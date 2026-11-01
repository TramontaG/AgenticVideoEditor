"""Reusable video processing; originals are never overwritten."""

import json
import math
from fractions import Fraction
from pathlib import Path
import re
import subprocess
import tempfile

from editor import digest, model_env, no_overwrite, probe, run, write


def video_info(source, requested_fps=None):
    metadata = probe(source)
    video = next((s for s in metadata["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ValueError("Input must contain a video stream")
    fps = None
    candidates = (
        [requested_fps]
        if requested_fps
        else [video.get("avg_frame_rate"), video.get("r_frame_rate")]
    )
    for candidate in candidates:
        try:
            value = Fraction(str(candidate))
            if value > 0:
                fps = value
                break
        except (ValueError, ZeroDivisionError):
            continue
    if fps is None:
        raise ValueError(
            "FPS must be positive; specify --fps if the source has no valid frame rate"
        )
    duration = video.get("duration")
    tagged_duration = video.get("tags", {}).get("DURATION")
    if not duration and tagged_duration:
        hours, minutes, seconds = tagged_duration.split(":")
        duration = (
            int(hours) * 3600
            + int(minutes) * 60
            + float(seconds)
            - float(video.get("start_time", 0))
        )
    duration = float(duration or metadata["format"].get("duration", 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Input has no finite positive duration")
    return metadata, video, fps, duration


def has_alpha(video):
    tags = video.get("tags", {})
    return (
        video.get("pix_fmt", "").startswith(
            ("rgba", "bgra", "argb", "abgr", "gbrap", "yuva", "ya", "pal8")
        )
        or str(tags.get("alpha_mode", tags.get("ALPHA_MODE", "0"))) == "1"
    )


def codec_options(output, transparent=False):
    suffix = Path(output).suffix.lower()
    if suffix == ".webm":
        return [
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            "-b:v",
            "0",
            "-crf",
            "18",
            "-auto-alt-ref",
            "0",
            "-threads",
            "2",
            "-c:a",
            "libopus",
            "-b:a",
            "192k",
        ]
    if suffix == ".mov":
        return [
            "-c:v",
            "prores_ks",
            "-profile:v",
            "4",
            "-pix_fmt",
            "yuva444p10le",
            "-threads",
            "2",
            "-c:a",
            "pcm_s16le",
        ]
    if suffix == ".mp4" and not transparent:
        return [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            "-threads",
            "2",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
        ]
    raise ValueError("Use .webm or .mov for transparency; opaque videos also support .mp4")


def video_geometry(video, max_width=None):
    width, height = video["width"], video["height"]
    sar = video.get("sample_aspect_ratio", "1:1").replace(":", "/")
    if sar not in ("N/A", "0/1"):
        width = round(width * float(Fraction(sar)))
    rotation = float(video.get("tags", {}).get("rotate", 0))
    for item in video.get("side_data_list", []):
        rotation = float(item.get("rotation", rotation))
    if abs(rotation) % 180 == 90:
        width, height = height, width
    if max_width:
        if max_width < 2:
            raise ValueError("max-width must be at least 2")
        scale = min(1, max_width / width)
        width, height = round(width * scale), round(height * scale)
    return max(2, width // 2 * 2), max(2, height // 2 * 2)


def _stop(process):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    for stream in (process.stdin, process.stdout):
        if stream:
            try:
                stream.close()
            except BrokenPipeError:
                pass


def _paths(source, output):
    source = Path(source).expanduser().resolve()
    output = no_overwrite(Path(output).expanduser().absolute())
    sidecar = no_overwrite(str(output) + ".json")
    if source == output.resolve():
        raise ValueError("Output must differ from input")
    return source, output, sidecar


def remove_video_background(root, source, output, model="u2netp", fps=None, max_width=None):
    source, output, sidecar = _paths(source, output)
    codec = codec_options(output, transparent=True)
    metadata, video, rate, _ = video_info(source, fps)
    width, height = video_geometry(video, max_width)
    audio = any(s["codec_type"] == "audio" for s in metadata["streams"])
    model_env(root)
    from PIL import Image
    from rembg import new_session, remove

    session = new_session(model, providers=["CPUExecutionProvider"])
    count = 0
    decoder = encoder = None
    with tempfile.TemporaryDirectory(prefix=".background-", dir=output.parent) as temporary:
        folder = Path(temporary)
        encoded = folder / output.name
        with (
            (folder / "decode.log").open("wb") as decode_log,
            (folder / "encode.log").open("wb") as encode_log,
        ):
            try:
                decoder = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-v",
                        "error",
                        "-i",
                        str(source),
                        "-an",
                        "-vf",
                        f"fps={rate},scale={width}:{height},setsar=1",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "pipe:1",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=decode_log,
                )
                command = [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-n",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgba",
                    "-s",
                    f"{width}x{height}",
                    "-r",
                    str(rate),
                    "-i",
                    "pipe:0",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0?",
                    *codec,
                ]
                if audio:
                    command += ["-af", "apad", "-shortest"]
                command += [str(encoded)]
                encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=encode_log)
                while True:
                    pixels = decoder.stdout.read(width * height * 3)
                    if not pixels:
                        break
                    if len(pixels) != width * height * 3:
                        raise RuntimeError("Decoder returned an incomplete frame")
                    with Image.frombytes("RGB", (width, height), pixels) as image:
                        cutout = remove(image, session=session).convert("RGBA")
                        try:
                            encoder.stdin.write(cutout.tobytes())
                        finally:
                            cutout.close()
                    count += 1
                encoder.stdin.close()
                if decoder.wait() or encoder.wait() or count == 0:
                    raise RuntimeError("Video decoding or encoding failed")
            except (RuntimeError, BrokenPipeError) as error:
                _stop(decoder)
                _stop(encoder)
                details = (folder / "decode.log").read_text(errors="replace") + (
                    folder / "encode.log"
                ).read_text(errors="replace")
                raise RuntimeError(
                    f"Background removal failed: {details[-4000:] or error}"
                ) from error
            finally:
                _stop(decoder)
                _stop(encoder)
        result_metadata = probe(encoded)
        encoded_video = next(s for s in result_metadata["streams"] if s["codec_type"] == "video")
        if not has_alpha(encoded_video):
            raise RuntimeError("The encoded video has no alpha channel")
        if audio and not any(s["codec_type"] == "audio" for s in result_metadata["streams"]):
            raise RuntimeError("The encoded video lost its audio stream")
        result = {
            "operation": "remove-video-background",
            "source": str(source),
            "sourceSha256": digest(source),
            "output": str(output),
            "model": model,
            "device": "cpu",
            "temporalModel": False,
            "fps": str(rate),
            "frames": count,
            "width": width,
            "height": height,
            "transparent": True,
            "audioPreserved": audio,
            "duration": count / float(rate),
        }
        encoded.replace(output)
        write(sidecar, result)
        return result


def detect_silence(source, noise_db=-35, min_silence=0.5):
    if not math.isfinite(noise_db) or not -120 <= noise_db <= 0:
        raise ValueError("noise-db must be between -120 and 0")
    if not math.isfinite(min_silence) or min_silence <= 0:
        raise ValueError("min-silence must be positive")
    log = run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-i",
            source,
            "-map",
            "0:a:0",
            "-vn",
            "-af",
            f"aresample=48000:async=1:first_pts=0,silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ]
    ).stderr
    intervals = []
    start = None
    for kind, value in re.findall(
        r"silence_(start|end):\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", log
    ):
        if kind == "start":
            start = float(value)
        elif start is not None:
            intervals.append([start, float(value)])
            start = None
    if start is not None:
        intervals.append([start, math.inf])
    return intervals


def frame_aligned_plan(duration, silence, padding, fps):
    if not math.isfinite(padding) or padding < 0:
        raise ValueError("padding must be nonnegative")
    rate = float(fps)
    total_frames = math.ceil(duration * rate - 1e-7)
    removed = []
    for start, end in sorted(silence):
        first = 0 if start <= 0.001 else math.ceil((start + padding) * rate - 1e-7)
        last = (
            total_frames if end >= duration - 0.001 else math.floor((end - padding) * rate + 1e-7)
        )
        first, last = max(0, first), min(total_frames, last)
        if last > first:
            removed.append((first, last))
    cursor = 0
    output_frame = 0
    ranges = []
    for first, last in [*removed, (total_frames, total_frames)]:
        if first > cursor:
            length = first - cursor
            ranges.append(
                {
                    "sourceStartFrame": cursor,
                    "sourceEndFrame": first,
                    "sourceStart": cursor / rate,
                    "sourceEnd": first / rate,
                    "outputStart": output_frame / rate,
                    "outputEnd": (output_frame + length) / rate,
                }
            )
            output_frame += length
        cursor = max(cursor, last)
    return {
        "fps": str(fps),
        "padding": padding,
        "duration": output_frame / rate,
        "durationInFrames": output_frame,
        "ranges": ranges,
    }


def remove_video_silence(source, output, noise_db=-35, min_silence=0.5, padding=0.15, fps=None):
    source, output, sidecar = _paths(source, output)
    metadata, video, rate, duration = video_info(source, fps)
    if not any(s["codec_type"] == "audio" for s in metadata["streams"]):
        raise ValueError("Cannot detect silence: the input video has no audio stream")
    codec = codec_options(output, transparent=has_alpha(video))
    intervals = detect_silence(source, noise_db, min_silence)
    plan = frame_aligned_plan(duration, intervals, padding, rate)
    if not plan["ranges"]:
        raise ValueError("No non-silent content remains; no output was created")
    n = len(plan["ranges"])
    # Normalize to one frame clock before splitting; cut audio and video at the same boundaries.
    graph = [
        f"[0:v:0]fps=fps={rate}:start_time=0,pad=ceil(iw/2)*2:ceil(ih/2)*2,setpts=PTS-STARTPTS,split={n}"
        + "".join(f"[v{i}]" for i in range(n)),
        f"[0:a:0]aresample=48000:async=1:first_pts=0,asplit={n}"
        + "".join(f"[a{i}]" for i in range(n)),
    ]
    for i, item in enumerate(plan["ranges"]):
        graph += [
            f"[v{i}]trim=start_frame={item['sourceStartFrame']}:end_frame={item['sourceEndFrame']},setpts=PTS-STARTPTS[vout{i}]",
            f"[a{i}]atrim=start={item['sourceStart']:.9f}:end={item['sourceEnd']:.9f},asetpts=PTS-STARTPTS,apad=whole_dur={item['outputEnd'] - item['outputStart']:.9f},atrim=duration={item['outputEnd'] - item['outputStart']:.9f}[aout{i}]",
        ]
    graph += ["".join(f"[vout{i}][aout{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"]
    with tempfile.TemporaryDirectory(prefix=".silence-", dir=output.parent) as temporary:
        folder = Path(temporary)
        script = folder / "cuts.ffscript"
        script.write_text(";\n".join(graph), encoding="utf-8")
        encoded = folder / output.name
        decoder = (
            ["-c:v", "libvpx-vp9"] if video.get("codec_name") == "vp9" and has_alpha(video) else []
        )
        run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-n",
                *decoder,
                "-i",
                source,
                "-filter_complex_script",
                script,
                "-map",
                "[v]",
                "-map",
                "[a]",
                *codec,
                "-r",
                str(rate),
                "-frames:v",
                str(plan["durationInFrames"]),
                encoded,
            ]
        )
        checked = probe(encoded)
        actual_duration = float(checked["format"]["duration"])
        if abs(actual_duration - plan["duration"]) > max(0.15, 2 / float(rate)):
            raise RuntimeError("Edited duration differs from the cut map; output was not published")
        result = {
            "operation": "remove-video-silence",
            "source": str(source),
            "sourceSha256": digest(source),
            "output": str(output),
            "noiseDb": noise_db,
            "minSilence": min_silence,
            "originalDuration": duration,
            "removedSeconds": max(0, duration - plan["duration"]),
            **plan,
        }
        encoded.replace(output)
        write(sidecar, result)
        return result


def print_result(result):
    print(json.dumps(result, ensure_ascii=False, indent=2))
