# Commands

Use `python scripts/editor.py --root <runtime> ...` for stdlib commands and runtime `tools/.venv/bin/python` (Windows `tools/.venv/Scripts/python.exe`) for model commands. Root may be omitted after setup.

```
editor.py init demo --orientation portrait --quality FHD --fps 30
editor.py ingest <project-dir> <source-path>
editor.py analyze <input-video> <analysis-dir> --threshold 0.3 --interval 10
editor.py transcribe <input-media> <output-stem> --model base --language pt
editor.py remove-bg <input-image> <output.png> --model u2netp
editor.py remove-bg <input-video> <output.webm> --video --model u2netp --fps 30
editor.py silence-plan <analysis.json> <edit-map.json> --padding 0.15
editor.py normalize <input-media> <output.mp4>
editor.py check <output.mp4> <qa.json>
editor.py snapshot <project-dir> --reason "Before changing the opening"
editor.py pexels-key
editor.py pexels-search "city at night" --kind videos
editor.py pexels-download <project> <candidate-json> --authorization "User's actual authorization"
```

`analyze` saves `analysis.json` plus cut and periodic reference frames, with original times in their filenames. Use a reasonable periodic interval for long files. `silence-plan` creates kept source ranges and source-to-output mapping, without overwriting the media. Apply those ranges as separate video/audio clips in the Remotion manifest; preserve padding around speech.

From the runtime `tools/` directory:

```
node motion-render.mjs <project> <asset-id> --width 1920 --height 1080 --fps 30 --duration 2
node motion-render.mjs <project> <asset-id> --format png
node render.mjs <project> --preview
node render.mjs <project>
```

The motion renderer initializes a usable scene if missing. Edit `<project>/motion/<asset-id>/scene.tsx` and its project module, rerun, and reference the resulting WebM using the `clip` object saved in `public/motion/<asset-id>/render.json`. The default is VP9 WebM with real alpha and `transparent: true`; frames stream directly into FFmpeg, so no PNG sequence is written to disk. `--crf 18` is the default quality; lower values increase quality and file size. `--crf 0` requests lossless VP9. `--format png` retains an explicit image-sequence option and returns a `frames` clip. Temporary output is removed after success or a handled failure; an existing video is replaced only after the new encode passes validation. Existing PNG assets are not deleted automatically because older timelines may still reference them. Options for orientation/resolution are explicit; do not silently mismatch the timeline. Cached identical renders are reused. Remotion preview uses half scale; final uses the exact manifest dimensions. Optional `--output <path>` changes the export destination. A timestamped name avoids overwriting prior exports.

## Dedicated video processing scripts

```
python scripts/remove_video_background.py input.mp4 output.webm --model u2netp
python scripts/remove_video_background.py input.mp4 output.webm --fps 30 --max-width 1280
python scripts/remove_video_silence.py input.mp4 edited.mp4 --noise-db -35 --min-silence 0.5 --padding 0.15
```

Both scripts can choose an output filename when it is omitted. Background removal defaults to transparent VP9 WebM and reuses the runtime Python environment automatically; `.mov` selects ProRes 4444. It streams frames through memory, preserves the primary audio stream, and saves an `<output>.json` processing report.

Silence removal exports the edited video, cutting audio and video together at frame-aligned boundaries. Its `<output>.json` includes kept source ranges and output timestamps for retiming subtitles. The default output is MP4 for opaque sources or WebM for sources with alpha; transparent inputs must use WebM or MOV. A video without audio or with no remaining audible content produces an error instead of an empty export. Adjust the silence threshold for the actual recording and review the cut points. Sources and existing outputs are never overwritten. Partial processing files are cleaned up on handled errors.

## Web page screenshots as assets

```
python scripts/capture_page.py <project> article https://example.com --full-page --width 1920
python scripts/capture_page.py <project> card https://example.com --selector "main .card" --scale 2
python scripts/capture_page.py <project> headline https://example.com --wait-for "h1" --format webp --quality 90
```

The Python entry point selects the installed runtime; `--root` chooses another one. The backend can also be run from `tools/` as `node capture-page.mjs <project> <asset-id> <url> [options]`. Run setup with `--update-toolchain` after updating an existing skill installation. No additional screenshot dependency is needed: this uses the existing Puppeteer/Chrome and FFprobe.

If Linux reports `No usable sandbox`, set `AI_EDITOR_BROWSER` to a locally installed Chrome executable with working sandbox support (for example `/opt/google/chrome/chrome` on Ubuntu). Do not disable the browser sandbox or system security settings to capture web pages. See the [Chromium sandbox documentation](https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md).

Captures are saved under `public/web/<asset-id>/capture.png` (or JPG/WebP), with `capture.json` containing the original/final URL, page title, timestamp, actual image dimensions, capture settings, warnings and an image clip descriptor. The asset is registered in `project.json`; the timeline is left for the agent to compose. Use a new asset ID for a revised capture; existing captures are protected.

Options: `--width`, `--height`, and `--scale` configure the viewport and pixel density. `--full-page` captures the entire document; `--selector` captures the first matching visible element. These two modes are exclusive. `--wait-for` waits for an element, `--wait-ms` adds up to 10 seconds for late rendering, and `--timeout-ms` controls navigation/selector timeouts. `--scroll` preloads lazy content with up to 20 scroll steps; full-page mode also performs this bounded preload. Review warnings when the page keeps loading or reaches the scroll limit.

PNG is the default; JPEG/WebP accept `--quality`. `--transparent` omits the browser's default background in PNG/WebP, but does not remove backgrounds drawn by the website itself. Captures use a fresh anonymous browser and do not reuse personal sessions or log in. HTTP(S) and localhost are supported. Login pages and challenges require user handling; the script does not bypass them. Review the actual screenshot before using it in the video.
