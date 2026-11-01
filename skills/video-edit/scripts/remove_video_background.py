#!/usr/bin/env python3
"""Remove a video's background locally, preserving alpha and source audio."""

import argparse
from pathlib import Path
import subprocess
import sys

from editor import root_path
from video_processing import print_result, remove_video_background


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--root")
    parser.add_argument("--model", default="u2netp")
    parser.add_argument("--fps", help="Output FPS; defaults to source FPS, e.g. 30 or 30000/1001")
    parser.add_argument(
        "--max-width", type=int, help="Optional downscale to reduce CPU processing cost"
    )
    args = parser.parse_args()
    root = root_path(args.root)
    venv = (
        root / "tools/.venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    if venv.exists() and Path(sys.executable).absolute() != venv.absolute():
        sys.exit(subprocess.call([str(venv), __file__, *sys.argv[1:]]))
    source = Path(args.source)
    output = args.output or source.with_name(source.stem + "-no-background.webm")
    print_result(
        remove_video_background(root, source, output, args.model, args.fps, args.max_width)
    )


if __name__ == "__main__":
    main()
