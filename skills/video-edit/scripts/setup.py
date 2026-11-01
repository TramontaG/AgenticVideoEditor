#!/usr/bin/env python3
"""Install and verify a user-local, portable video editing runtime."""

import argparse
import datetime as dt
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import wave

from editor import (
    CONFIG,
    analyze,
    check,
    init_project,
    ingest,
    model_env,
    normalize,
    probe,
    read,
    remove_bg,
    root_path,
    silence_plan,
    transcribe,
    write,
)

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "toolchain"


def execute(args, cwd=None, env=None):
    # npm is a .cmd launcher on Windows. Resolve it explicitly for subprocess.
    args = [str(x) for x in args]
    args[0] = shutil.which(args[0]) or args[0]
    subprocess.run(args, cwd=cwd, env=env, check=True)


def executable_version(name, flag="--version"):
    exe = shutil.which(name)
    if not exe:
        return {"available": False}
    result = subprocess.run([exe, flag], capture_output=True, text=True)
    return {
        "available": result.returncode == 0,
        "path": exe,
        "version": (result.stdout or result.stderr).splitlines()[:1],
    }


def python_executable(tools):
    return tools / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_interpreter(root, command, allow_bootstrap=False):
    if command in ("models", "smoke"):
        venv = python_executable(root / "tools")
        if venv.exists() and Path(sys.executable).absolute() != venv.absolute():
            sys.exit(subprocess.call([str(venv), __file__, *sys.argv[1:]]))
    if command != "install" or (3, 11) <= sys.version_info[:2] < (3, 14):
        return
    for name in ["python3.12", "python3.13", "python3.11"]:
        candidate = shutil.which(name)
        if candidate:
            sys.exit(subprocess.call([candidate, __file__, *sys.argv[1:]]))
    if os.name == "nt" and shutil.which("py"):
        for version in ["-3.12", "-3.13", "-3.11"]:
            found = subprocess.run(
                ["py", version, "-c", "import sys;print(sys.executable)"],
                capture_output=True,
                text=True,
            )
            if found.returncode == 0:
                sys.exit(subprocess.call([found.stdout.strip(), __file__, *sys.argv[1:]]))
    if not allow_bootstrap:
        raise RuntimeError(
            "No compatible Python found. Rerun install with --install-system to download an isolated Python 3.12 through uv."
        )
    bootstrap = root / "tools/bootstrap"
    execute([sys.executable, "-m", "pip", "install", "--target", bootstrap, "uv==0.13.6"])
    env = dict(
        os.environ,
        PYTHONPATH=str(bootstrap),
        UV_PYTHON_INSTALL_DIR=str(root / "tools/python"),
        UV_PYTHON_BIN_DIR=str(root / "tools/bin"),
        UV_CACHE_DIR=str(root / "tools/.uv-cache"),
    )
    execute([sys.executable, "-m", "uv", "python", "install", "3.12"], env=env)
    candidate = subprocess.check_output(
        [sys.executable, "-m", "uv", "python", "find", "3.12"], env=env, text=True
    ).strip()
    sys.exit(subprocess.call([candidate, __file__, *sys.argv[1:]], env=env))


def doctor(root):
    report = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "root": str(root),
        "python": sys.version.split()[0],
        "tools": {},
        "cpuCount": os.cpu_count(),
        "freeDiskBytes": shutil.disk_usage(root if root.exists() else Path.home()).free,
        "inferenceDefault": "cpu",
        "validation": "not_run",
    }
    if hasattr(os, "sysconf"):
        try:
            report["memoryBytes"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError):
            pass
    for name in ["node", "npm", "ffmpeg", "ffprobe"]:
        report["tools"][name] = executable_version(
            name, "-version" if name.startswith("ff") else "--version"
        )
    gpu = shutil.which("nvidia-smi")
    if gpu:
        result = subprocess.run(
            [gpu, "--query-gpu=name,memory.total,driver_version", "--format=csv"],
            capture_output=True,
            text=True,
        )
        report["nvidia"] = {
            "available": result.returncode == 0,
            "detail": (result.stdout or result.stderr).strip()[:1200],
        }
    venv = python_executable(root / "tools")
    report["nodePackages"] = {}
    for name in ["remotion", "@motion-canvas/core", "@motion-canvas/ffmpeg"]:
        package = root / "tools/node_modules" / name / "package.json"
        report["nodePackages"][name] = read(package)["version"] if package.exists() else None
    model_report = root / "logs/models.json"
    report["models"] = read(model_report).get("loaded", []) if model_report.exists() else []
    report["venv"] = {"available": venv.exists(), "path": str(venv)}
    if venv.exists():
        result = subprocess.run([str(venv), "-m", "pip", "check"], capture_output=True, text=True)
        report["venv"]["pipCheck"] = {"ok": result.returncode == 0, "detail": result.stdout.strip()}
    return report


def install_system():
    system = platform.system()
    need_node = (
        not shutil.which("node")
        or int(
            subprocess.check_output(["node", "--version"], text=True)
            .strip()
            .lstrip("v")
            .split(".")[0]
        )
        < 22
    )
    need_ffmpeg = not shutil.which("ffmpeg") or not shutil.which("ffprobe")
    if not need_node and not need_ffmpeg:
        return
    if system == "Darwin" and shutil.which("brew"):
        execute(
            [
                "brew",
                "install",
                *(["node"] if need_node else []),
                *(["ffmpeg"] if need_ffmpeg else []),
            ]
        )
    elif system == "Windows" and shutil.which("winget"):
        if need_node:
            execute(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "OpenJS.NodeJS.LTS",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )
        if need_ffmpeg:
            execute(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "Gyan.FFmpeg",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )
        # winget may update user/system PATH without updating this process.
        try:
            import winreg

            parts = []
            for hive, key in [
                (
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                ),
                (winreg.HKEY_CURRENT_USER, r"Environment"),
            ]:
                with winreg.OpenKey(hive, key) as registry:
                    parts.append(os.path.expandvars(winreg.QueryValueEx(registry, "Path")[0]))
            os.environ["PATH"] = os.pathsep.join(parts + [os.environ["PATH"]])
        except OSError:
            pass
    elif system == "Linux":
        sudo = [] if hasattr(os, "geteuid") and os.geteuid() == 0 else ["sudo"]
        packages = (["nodejs", "npm"] if need_node else []) + (["ffmpeg"] if need_ffmpeg else [])
        if shutil.which("apt-get"):
            execute([*sudo, "apt-get", "update"])
            execute([*sudo, "apt-get", "install", "-y", *packages])
        elif shutil.which("dnf"):
            execute([*sudo, "dnf", "install", "-y", *packages])
        elif shutil.which("pacman"):
            execute([*sudo, "pacman", "-S", "--needed", "--noconfirm", *packages])
        else:
            raise RuntimeError(
                "No supported Linux package manager; install Node >=22 and FFmpeg using the OS documentation"
            )
    else:
        raise RuntimeError(
            "Install a supported package manager (Homebrew/winget) or Node >=22 and FFmpeg, then rerun"
        )


def copy_templates(source, tools, update=False):
    excluded = {"node_modules", ".venv", ".vite", ".remotion", "__pycache__", "template-backups"}
    backup = tools / "template-backups" / dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for directory, folders, files in os.walk(source):
        folders[:] = [name for name in folders if name not in excluded]
        for name in files:
            item = Path(directory) / name
            relative = item.relative_to(source)
            target = tools / relative
            if target.exists():
                if not update or target.read_bytes() == item.read_bytes():
                    continue
                saved = backup / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
    return str(backup) if backup.exists() else None


def install(root, allow_system=False, download=False, update=False):
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise RuntimeError("Run this installer with Python 3.11–3.13; do not replace system Python")
    if allow_system:
        install_system()
    report = doctor(root)
    missing = [name for name, status in report["tools"].items() if not status["available"]]
    if missing:
        raise RuntimeError(
            "Missing prerequisites: "
            + ", ".join(missing)
            + ". Rerun with --install-system when authorized."
        )
    if (
        int(subprocess.check_output(["node", "--version"], text=True).lstrip("v").split(".")[0])
        < 22
    ):
        raise RuntimeError(
            "Node >=22 required; update using the OS package manager or existing version manager"
        )
    for folder in ["tools", "models", "projects", "styles", "workflows", "logs", "config"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
    tools = root / "tools"
    backup = copy_templates(ASSETS, tools, update=update)
    (root / ".gitignore").write_text(
        "config/\nmodels/\ntools/node_modules/\ntools/.venv/\nlogs/\n**/exports/\n",
        encoding="utf-8",
    ) if not (root / ".gitignore").exists() else None
    venv = python_executable(tools)
    if not venv.exists():
        execute([sys.executable, "-m", "venv", tools / ".venv"])
    execute(
        [
            "npm",
            "ci" if (tools / "package-lock.json").exists() else "install",
            "--prefix",
            tools,
            "--no-audit",
            "--no-fund",
        ],
        cwd=tools,
    )
    requirements = tools / "requirements.lock.txt"
    execute(
        [
            venv,
            "-m",
            "pip",
            "install",
            "-r",
            requirements if requirements.exists() else tools / "requirements.txt",
        ]
    )
    frozen = subprocess.check_output([str(venv), "-m", "pip", "freeze"], text=True)
    requirements.write_text(frozen, encoding="utf-8")
    browser = os.getenv("AI_EDITOR_BROWSER")
    if not browser:
        execute(
            ["node", tools / "node_modules/@remotion/cli/remotion-cli.js", "browser", "ensure"],
            cwd=tools,
        )
    write(CONFIG, {"root": str(root)})
    if download:
        execute([venv, __file__, "models", "--root", root])
    report = doctor(root)
    report["validation"] = "installed_smoke_required"
    if backup:
        report["templateBackup"] = backup
    write(root / "logs/environment.json", report)
    return report


def models(root):
    model_env(root)
    from faster_whisper import WhisperModel
    from rembg import new_session

    WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        download_root=str(root / "models/whisper"),
    )
    new_session("u2netp", providers=["CPUExecutionProvider"])
    from editor import digest

    files = [
        {"file": str(p.relative_to(root)), "size": p.stat().st_size, "sha256": digest(p)}
        for p in (root / "models").rglob("*")
        if p.is_file() and not p.is_symlink() and p.stat().st_size > 1024 * 1024
    ]
    record = {
        "loaded": ["faster-whisper/base:cpu:int8", "rembg/u2netp:cpu"],
        "files": files,
        "sources": [
            "https://huggingface.co/Systran/faster-whisper-base",
            "https://github.com/danielgatis/rembg",
        ],
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["faster-whisper", "rembg", "onnxruntime"]
        },
    }
    write(root / "logs/models.json", record)
    return record


def smoke(root):
    tools = root / "tools"
    project = init_project(
        root, "smoke-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f"), quality="HD"
    )
    results = {"project": str(project), "checks": {}}
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (320, 240), "white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((100, 20, 220, 140), fill="#2563eb")
        draw.rectangle((80, 140, 240, 235), fill="#2563eb")
        fixture = project / "originals/synthetic.png"
        image.save(fixture)
        remove_bg(root, fixture, project / "public/media/cutout.png")
        with Image.open(project / "public/media/cutout.png") as cutout:
            assert cutout.mode == "RGBA" and cutout.getextrema()[3][0] < 255, "Alpha output missing"
        results["checks"]["imageBackgroundInference"] = True
        wav = project / "originals/silence.wav"
        with wave.open(str(wav), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b"\x00\x00" * 16000 * 4)
        results["checks"]["transcriptionInference"] = transcribe(
            root, wav, project / "analysis/transcript", "base", language="en"
        )
        source = project / "originals/scenes.mp4"
        execute(
            [
                "ffmpeg",
                "-v",
                "error",
                "-n",
                "-f",
                "lavfi",
                "-i",
                "color=red:s=640x360:r=30:d=2",
                "-f",
                "lavfi",
                "-i",
                "color=blue:s=640x360:r=30:d=2",
                "-i",
                wav,
                "-filter_complex",
                "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map",
                "[v]",
                "-map",
                "2:a",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                source,
            ]
        )
        asset = ingest(project, source)
        report = analyze(source, project / "analysis/scenes", threshold=0.1, interval=1)
        assert any(1.9 < t < 2.1 for t in report["sceneCuts"]), "Known scene cut was not detected"
        assert report["silence"], "Known silence missing"
        results["checks"]["sceneAndSilenceDetection"] = True
        write(project / "analysis/edit-map.json", silence_plan(report, 0.15))
        normalize(source, project / "public/media/normalized.mp4")
        results["checks"]["normalization"] = True
        execute(
            [
                "node",
                tools / "motion-render.mjs",
                project,
                "demo",
                "--width",
                "1280",
                "--height",
                "720",
                "--fps",
                "30",
                "--duration",
                "2",
            ],
            cwd=tools,
        )
        animation = read(project / "public/motion/demo/render.json")
        manifest = read(project / "timeline/manifest.json")
        manifest["durationInFrames"] = 120
        manifest["clips"] = [
            {
                "id": "footage",
                "type": "video",
                "src": asset["src"],
                "from": 0,
                "durationInFrames": 120,
                "volume": 0.5,
            },
            {
                "id": "motion",
                **animation["clip"],
                "from": 0,
                "durationInFrames": 60,
                "objectFit": "contain",
            },
            {
                "id": "cutout",
                "type": "image",
                "src": "media/cutout.png",
                "from": 60,
                "durationInFrames": 60,
                "width": 320,
                "height": 240,
                "x": 480,
                "y": 240,
            },
        ]
        write(project / "timeline/manifest.json", manifest)
        output = project / "exports/integration.mp4"
        execute(["node", tools / "render.mjs", project, "--output", output], cwd=tools)
        alpha_sample = project / "analysis/motion-alpha.png"
        execute(
            [
                "ffmpeg",
                "-v",
                "error",
                "-n",
                "-c:v",
                "libvpx-vp9",
                "-i",
                project / "public" / animation["src"],
                "-vf",
                "select=eq(n\\,30)",
                "-frames:v",
                "1",
                alpha_sample,
            ]
        )
        with Image.open(alpha_sample) as sample:
            assert sample.mode == "RGBA" and sample.getpixel((0, 0))[3] == 0, (
                "Transparent animation background missing"
            )
            assert sample.getextrema()[3][1] == 255, "Opaque animation content missing"
        composition_sample = project / "analysis/composited.png"
        execute(
            [
                "ffmpeg",
                "-v",
                "error",
                "-n",
                "-ss",
                "1",
                "-i",
                output,
                "-frames:v",
                "1",
                composition_sample,
            ]
        )
        with Image.open(composition_sample) as sample:
            red, green, blue = sample.convert("RGB").getpixel((10, 10))
            assert red > 230 and green < 25 and blue < 25, (
                "Video alpha did not reveal the background footage"
            )
        assert not list((project / "public/motion/demo").rglob("*.png")), (
            "Default render left PNG frames on disk"
        )
        results["checks"]["transparentAnimation"] = True
        metadata = probe(output)
        stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
        assert (stream["width"], stream["height"]) == (1280, 720), "Unexpected output dimensions"
        assert abs(float(metadata["format"]["duration"]) - 4) < 0.15, "Unexpected duration"
        check(output, project / "exports/qa.json")
        results["checks"]["motionCanvasToRemotion"] = True
        results["output"] = str(output)
        results["status"] = "passed"
        environment = doctor(root)
        environment["validation"] = "smoke_passed"
        environment["smokeReport"] = str(root / "logs/smoke.json")
        write(root / "logs/environment.json", environment)
    except Exception as exc:
        results["status"] = "failed"
        results["error"] = str(exc)
        raise
    finally:
        write(root / "logs/smoke.json", results)
        write(project / "analysis/smoke.json", results)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "install", "models", "smoke"])
    parser.add_argument("--root")
    parser.add_argument("--install-system", action="store_true")
    parser.add_argument("--download-models", action="store_true")
    parser.add_argument(
        "--update-toolchain",
        action="store_true",
        help="Back up and replace bundled templates in an existing installation",
    )
    args = parser.parse_args()
    root = root_path(args.root)
    ensure_interpreter(root, args.command, args.install_system)
    if args.command == "doctor":
        result = doctor(root)
    elif args.command == "install":
        result = install(root, args.install_system, args.download_models, args.update_toolchain)
    elif args.command == "models":
        result = models(root)
    else:
        result = smoke(root)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
