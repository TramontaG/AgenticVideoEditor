#!/usr/bin/env python3
"""Capture an HTTP(S) page as a reusable image asset in a video project."""

import argparse
from pathlib import Path
import shutil
import subprocess
from editor import root_path


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Additional flags are passed to capture-page.mjs: --full-page, --selector, --width, --height, --scale, --wait-for, --wait-ms, --scroll, --format, --quality, --transparent.",
    )
    parser.add_argument("project")
    parser.add_argument("asset_id")
    parser.add_argument("url")
    parser.add_argument("--root")
    value_options = (
        "width",
        "height",
        "scale",
        "selector",
        "wait-for",
        "wait-ms",
        "timeout-ms",
        "format",
        "quality",
    )
    boolean_options = ("full-page", "scroll", "transparent")
    for name in value_options:
        parser.add_argument("--" + name)
    for name in boolean_options:
        parser.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    options = []
    for name in value_options:
        value = getattr(args, name.replace("-", "_"))
        if value is not None:
            options.extend(["--" + name, value])
    for name in boolean_options:
        if getattr(args, name.replace("-", "_")):
            options.append("--" + name)
    tools = root_path(args.root) / "tools"
    backend = tools / "capture-page.mjs"
    node = shutil.which("node")
    if not node or not backend.exists():
        parser.error("Capture toolchain missing. Run setup.py install --update-toolchain first.")
    # Resolve before changing the working directory for the browser cache.
    project = Path(args.project).expanduser().resolve()
    subprocess.run(
        [node, str(backend), str(project), args.asset_id, args.url, *options], cwd=tools, check=True
    )


if __name__ == "__main__":
    main()
