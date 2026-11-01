#!/usr/bin/env python3
"""Cut long quiet passages from video and audio together; export a JSON cut map."""

import argparse
from pathlib import Path

from video_processing import print_result, remove_video_silence, video_info, has_alpha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output", nargs="?")
    parser.add_argument(
        "--noise-db", type=float, default=-35, help="Silence threshold in dB (default: -35)"
    )
    parser.add_argument("--min-silence", type=float, default=0.5, help="Minimum pause in seconds")
    parser.add_argument(
        "--padding", type=float, default=0.15, help="Margin around speech in seconds"
    )
    parser.add_argument("--fps", help="Output FPS; defaults to source FPS")
    args = parser.parse_args()
    source = Path(args.source)
    if args.output:
        output = args.output
    else:
        _, video, _, _ = video_info(source, args.fps)
        output = source.with_name(
            source.stem + "-no-silence" + (".webm" if has_alpha(video) else ".mp4")
        )
    print_result(
        remove_video_silence(
            source, output, args.noise_db, args.min_silence, args.padding, args.fps
        )
    )


if __name__ == "__main__":
    main()
