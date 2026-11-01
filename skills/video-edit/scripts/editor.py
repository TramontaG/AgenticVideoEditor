#!/usr/bin/env python3
"""Portable media helpers. Model dependencies are imported only on demand."""

import argparse
import datetime as dt
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request

CONFIG = Path.home() / ".config" / "ai-video-editor" / "config.json"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def root_path(value=None):
    value = value or os.getenv("AI_EDITOR_ROOT")
    if not value and CONFIG.exists():
        value = read(CONFIG).get("root")
    return Path(value).expanduser().resolve() if value else Path.home() / "Videos" / "AI-Editor"


def run(args):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:] or result.stdout[-6000:])
    return result


def probe(path):
    return json.loads(
        run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", path]).stdout
    )


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def no_overwrite(path):
    path = Path(path)
    if path.exists():
        raise ValueError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_project(root, slug, orientation="landscape", quality="FHD", fps=30):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", slug):
        raise ValueError("Project name must be a simple slug")
    project = root / "projects" / slug
    if project.exists():
        raise ValueError(f"Project already exists: {project}")
    w, h = {"HD": (1280, 720), "FHD": (1920, 1080), "QHD": (2560, 1440)}[quality]
    if orientation == "portrait":
        w, h = h, w
    for part in [
        "originals",
        "public/media",
        "public/motion",
        "motion",
        "timeline/history",
        "analysis",
        "exports",
    ]:
        (project / part).mkdir(parents=True, exist_ok=True)
    write(
        project / "project.json",
        {
            "version": 1,
            "id": slug,
            "created": dt.datetime.now(dt.timezone.utc).isoformat(),
            "assets": [],
        },
    )
    write(project / "decisions.json", {"style": None, "decisions": [], "stockAuthorizations": []})
    write(
        project / "timeline/manifest.json",
        {
            "version": 1,
            "width": w,
            "height": h,
            "fps": fps,
            "durationInFrames": fps * 5,
            "background": "#111827",
            "clips": [],
        },
    )
    return project


def ingest(project, source):
    project, source = Path(project), Path(source).resolve()
    data = read(project / "project.json")
    sha = digest(source)
    for asset in data["assets"]:
        if asset["sha256"] == sha:
            return asset
    asset_id = "asset-" + sha[:16]
    name = asset_id + source.suffix.lower()
    shutil.copy2(source, project / "originals" / name)
    shutil.copy2(source, project / "public/media" / name)
    asset = {
        "id": asset_id,
        "name": source.name,
        "sha256": sha,
        "original": "originals/" + name,
        "src": "media/" + name,
    }
    data["assets"].append(asset)
    write(project / "project.json", data)
    return asset


def analyze(source, destination, threshold=0.3, interval=10):
    source, dest = Path(source).resolve(), Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    info = probe(source)
    duration = float(info["format"].get("duration", 0))
    video = any(s["codec_type"] == "video" for s in info["streams"])
    audio = any(s["codec_type"] == "audio" for s in info["streams"])
    cuts, silent = [], []
    if video:
        log = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                source,
                "-an",
                "-vf",
                f"select=gt(scene\\,{threshold}),showinfo",
                "-fps_mode",
                "vfr",
                "-f",
                "null",
                "-",
            ]
        ).stderr
        cuts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", log)]
    if audio:
        log = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                source,
                "-vn",
                "-af",
                "silencedetect=noise=-35dB:d=0.5",
                "-f",
                "null",
                "-",
            ]
        ).stderr
        start = None
        for kind, value in re.findall(r"silence_(start|end): ([\d.]+)", log):
            if kind == "start":
                start = float(value)
            elif start is not None:
                silent.append([start, float(value)])
                start = None
        if start is not None:
            silent.append([start, duration])
    thumbs = []
    if video:
        times = sorted(
            {
                0.0,
                *[round(min(t + 0.08, max(0, duration - 0.1)), 3) for t in cuts],
                *[float(t) for t in range(interval, max(interval, math.ceil(duration)), interval)],
            }
        )
        for t in times:
            output = dest / f"frame-{t:010.3f}.jpg"
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-ss",
                    str(t),
                    "-i",
                    source,
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=640:-2",
                    "-q:v",
                    "3",
                    output,
                ]
            )
            if output.exists():
                thumbs.append({"time": t, "file": output.name})
    result = {
        "source": str(source),
        "sha256": digest(source),
        "metadata": info,
        "duration": duration,
        "sceneCuts": cuts,
        "silence": silent,
        "thumbnails": thumbs,
    }
    write(dest / "analysis.json", result)
    return result


def silence_plan(analysis, padding):
    duration = analysis["duration"]
    cursor, ranges = 0.0, []
    for start, end in sorted(analysis["silence"]):
        a, b = max(0, start + padding), min(duration, end - padding)
        if b <= a:
            continue
        if a > cursor:
            ranges.append([cursor, a])
        cursor = max(cursor, b)
    if cursor < duration:
        ranges.append([cursor, duration])
    out, items = 0.0, []
    for start, end in ranges:
        items.append(
            {
                "sourceStart": start,
                "sourceEnd": end,
                "outputStart": out,
                "outputEnd": out + end - start,
            }
        )
        out += end - start
    return {"duration": out, "padding": padding, "ranges": items}


def model_env(root):
    os.environ["REMBG_HOME"] = str(root / "models/rembg")
    os.environ["U2NET_HOME"] = str(root / "models/rembg")
    os.environ.setdefault("HF_HOME", str(root / "models/huggingface"))
    os.environ.setdefault("OMP_NUM_THREADS", "4")


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def transcribe(root, source, output, model, language=None):
    model_env(root)
    from faster_whisper import WhisperModel

    engine = WhisperModel(
        model,
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        download_root=str(root / "models/whisper"),
    )
    segments, info = engine.transcribe(
        str(source), language=language, word_timestamps=True, vad_filter=True
    )
    records, subtitles = [], []
    for i, s in enumerate(segments, 1):
        records.append(
            {
                "id": s.id,
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "words": [
                    {"start": w.start, "end": w.end, "word": w.word, "probability": w.probability}
                    for w in (s.words or [])
                ],
            }
        )
        subtitles.append(f"{i}\n{timestamp(s.start)} --> {timestamp(s.end)}\n{s.text.strip()}\n")
    stem = Path(output)
    no_overwrite(str(stem) + ".json")
    no_overwrite(str(stem) + ".srt")
    write(str(stem) + ".json", {"language": info.language, "model": model, "segments": records})
    Path(str(stem) + ".srt").write_text("\n".join(subtitles), encoding="utf-8")
    return {"segments": len(records), "language": info.language}


def remove_bg(root, source, output, model="u2netp", video=False, fps=30):
    model_env(root)
    from rembg import new_session, remove
    from PIL import Image

    session = new_session(model, providers=["CPUExecutionProvider"])
    source, output = Path(source), no_overwrite(output)
    if not video:
        with Image.open(source) as image:
            remove(image, session=session).save(output, format="PNG")
    else:
        if output.suffix.lower() != ".mov":
            raise ValueError("Video alpha output must be .mov (ProRes 4444)")
        with tempfile.TemporaryDirectory(prefix="ai-video-bg-") as tmp:
            folder = Path(tmp)
            run(["ffmpeg", "-v", "error", "-i", source, "-vf", f"fps={fps}", folder / "%06d.png"])
            for frame in sorted(folder.glob("*.png")):
                with Image.open(frame) as image:
                    cutout = remove(image, session=session)
                cutout.save(frame)
            run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-n",
                    "-framerate",
                    str(fps),
                    "-i",
                    folder / "%06d.png",
                    "-i",
                    source,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a?",
                    "-c:v",
                    "prores_ks",
                    "-profile:v",
                    "4",
                    "-pix_fmt",
                    "yuva444p10le",
                    "-c:a",
                    "pcm_s16le",
                    "-shortest",
                    output,
                ]
            )
    return {"output": str(output), "model": model, "temporalModel": False}


def normalize(source, output, fps=30):
    source, output = Path(source), no_overwrite(output)
    metadata = probe(source)
    video = any(s["codec_type"] == "video" for s in metadata["streams"])
    audio = any(s["codec_type"] == "audio" for s in metadata["streams"])
    args = ["ffmpeg", "-v", "error", "-n", "-i", source]
    if audio:
        measurement = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                source,
                "-vn",
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                "-f",
                "null",
                "-",
            ]
        ).stderr
        match = re.search(r'\{\s*"input_i".*?\}', measurement, re.S)
        values = json.loads(match.group()) if match else {}
        # Silence cannot be normalized to a finite loudness.
        if values and all(
            math.isfinite(float(values[k]))
            for k in ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"]
        ):
            filt = "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:" + ":".join(
                f"{key}={values[value]}"
                for key, value in [
                    ("measured_I", "input_i"),
                    ("measured_TP", "input_tp"),
                    ("measured_LRA", "input_lra"),
                    ("measured_thresh", "input_thresh"),
                    ("offset", "target_offset"),
                ]
            )
            args += ["-af", filt]
        args += ["-ar", "48000", "-c:a", "pcm_s16le" if output.suffix.lower() == ".wav" else "aac"]
    if video:
        args += [
            "-vf",
            f"fps={fps},scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
        ]
    args += [output]
    run(args)
    return {"output": str(output), "metadata": probe(output)}


def check(source, destination):
    metadata = probe(source)
    flags = ""
    if any(s["codec_type"] == "video" for s in metadata["streams"]):
        flags = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                source,
                "-an",
                "-vf",
                "blackdetect=d=0.3:pix_th=0.1,freezedetect=n=-50dB:d=2",
                "-f",
                "null",
                "-",
            ]
        ).stderr
    result = {
        "metadata": metadata,
        "candidates": [
            line for line in flags.splitlines() if "black_start:" in line or "freeze_" in line
        ],
        "visualReviewRequired": True,
        "audioReviewRequired": True,
    }
    write(destination, result)
    return result


def api_key(root):
    value = os.getenv("PEXELS_API_KEY")
    file = root / "config/credentials.json"
    if not value and file.exists():
        value = read(file).get("pexels")
    if not value:
        raise ValueError("Pexels key missing. Run pexels-key with hidden terminal input.")
    return value


def pexels_search(root, query, kind):
    endpoint = "videos/search" if kind == "videos" else "v1/search"
    request = urllib.request.Request(
        "https://api.pexels.com/"
        + endpoint
        + "?"
        + urllib.parse.urlencode({"query": query, "per_page": 8}),
        headers={"Authorization": api_key(root)},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    candidates = []
    for item in data[kind]:
        if kind == "videos":
            files = [x for x in item["video_files"] if x.get("file_type") == "video/mp4"]
            if not files:
                continue
            chosen = min(files, key=lambda x: abs((x.get("width") or 0) - 1920))
            url, creator, preview = chosen["link"], item["user"]["name"], item["image"]
        else:
            url, creator, preview = (
                item["src"]["original"],
                item["photographer"],
                item["src"]["medium"],
            )
        candidates.append(
            {
                "id": str(item["id"]),
                "kind": kind,
                "url": url,
                "page": item["url"],
                "creator": creator,
                "preview": preview,
                "width": item["width"],
                "height": item["height"],
            }
        )
    return candidates


def pexels_download(project, candidate, authorization):
    if not authorization.strip():
        raise ValueError("Actual user authorization or a recorded covering grant is required")
    url = urllib.parse.urlparse(candidate["url"])
    allowed = ("pexels.com", "pexels.io")
    if url.scheme != "https" or not any(
        url.hostname == d or (url.hostname or "").endswith("." + d) for d in allowed
    ):
        raise ValueError("Only HTTPS Pexels media domains are allowed")
    if candidate["kind"] not in ("videos", "photos") or not str(candidate["id"]).isdigit():
        raise ValueError("Invalid Pexels candidate")
    project = Path(project)
    decisions = read(project / "decisions.json")
    suffix = ".mp4" if candidate["kind"] == "videos" else ".jpg"
    name = "pexels-" + candidate["kind"] + "-" + candidate["id"] + suffix
    output = project / "public/media" / name
    for old in decisions["stockAuthorizations"]:
        if (
            old["candidate"]["id"] == candidate["id"]
            and old["candidate"]["url"] == candidate["url"]
            and output.exists()
        ):
            if digest(output) != old["sha256"]:
                raise ValueError("Previously downloaded asset changed; inspect before reuse")
            return old
    no_overwrite(output)
    temp = output.with_suffix(".download")
    # No Authorization header on media downloads, including redirects.
    with urllib.request.urlopen(candidate["url"], timeout=60) as response, temp.open("wb") as file:
        shutil.copyfileobj(response, file)
    temp.replace(output)
    record = {
        "candidate": candidate,
        "authorization": authorization,
        "date": dt.datetime.now(dt.timezone.utc).isoformat(),
        "src": "media/" + name,
        "sha256": digest(output),
    }
    decisions["stockAuthorizations"].append(record)
    write(project / "decisions.json", decisions)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("slug")
    p.add_argument("--orientation", choices=["landscape", "portrait"], default="landscape")
    p.add_argument("--quality", choices=["HD", "FHD", "QHD"], default="FHD")
    p.add_argument("--fps", type=int, default=30)
    p = sub.add_parser("ingest")
    p.add_argument("project")
    p.add_argument("source")
    p = sub.add_parser("analyze")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--threshold", type=float, default=0.3)
    p.add_argument("--interval", type=int, default=10)
    p = sub.add_parser("silence-plan")
    p.add_argument("analysis")
    p.add_argument("output")
    p.add_argument("--padding", type=float, default=0.15)
    p = sub.add_parser("transcribe")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--model", default="base")
    p.add_argument("--language")
    p = sub.add_parser("remove-bg")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--model", default="u2netp")
    p.add_argument("--video", action="store_true")
    p.add_argument("--fps", type=int, default=30)
    p = sub.add_parser("normalize")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--fps", type=int, default=30)
    p = sub.add_parser("check")
    p.add_argument("source")
    p.add_argument("output")
    p = sub.add_parser("snapshot")
    p.add_argument("project")
    p.add_argument("--reason", required=True)
    sub.add_parser("pexels-key")
    p = sub.add_parser("pexels-search")
    p.add_argument("query")
    p.add_argument("--kind", choices=["videos", "photos"], default="videos")
    p = sub.add_parser("pexels-download")
    p.add_argument("project")
    p.add_argument("candidate")
    p.add_argument("--authorization", required=True)
    a = parser.parse_args()
    root = root_path(a.root)
    if hasattr(a, "fps") and a.fps <= 0:
        parser.error("fps must be positive")
    if hasattr(a, "interval") and a.interval <= 0:
        parser.error("interval must be positive")
    if hasattr(a, "padding") and a.padding < 0:
        parser.error("padding must be nonnegative")
    if a.command == "init":
        result = str(init_project(root, a.slug, a.orientation, a.quality, a.fps))
    elif a.command == "ingest":
        result = ingest(a.project, a.source)
    elif a.command == "analyze":
        result = analyze(a.source, a.output, a.threshold, a.interval)
    elif a.command == "silence-plan":
        result = silence_plan(read(a.analysis), a.padding)
        write(a.output, result)
    elif a.command == "transcribe":
        result = transcribe(root, a.source, a.output, a.model, a.language)
    elif a.command == "remove-bg":
        result = remove_bg(root, a.source, a.output, a.model, a.video, a.fps)
    elif a.command == "normalize":
        result = normalize(a.source, a.output, a.fps)
    elif a.command == "check":
        result = check(a.source, a.output)
    elif a.command == "snapshot":
        project = Path(a.project)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        destination = project / "timeline/history" / (stamp + ".json")
        write(
            destination, {"reason": a.reason, "manifest": read(project / "timeline/manifest.json")}
        )
        result = {"snapshot": str(destination)}
    elif a.command == "pexels-search":
        result = pexels_search(root, a.query, a.kind)
    elif a.command == "pexels-download":
        result = pexels_download(a.project, read(a.candidate), a.authorization)
    else:
        secret = getpass.getpass("Pexels API key (hidden): ").strip()
        if not secret:
            raise ValueError("Empty key")
        dest = root / "config/credentials.json"
        data = read(dest) if dest.exists() else {}
        data["pexels"] = secret
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        if os.name != "nt":
            dest.chmod(0o600)
        result = {"saved": True}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
