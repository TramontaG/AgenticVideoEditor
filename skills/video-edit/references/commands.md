# Commands

Use `python scripts/editor.py --root <runtime> ...` for stdlib commands and runtime `tools/.venv/bin/python` (Windows `tools/.venv/Scripts/python.exe`) for model commands. Root may be omitted after setup.

```
editor.py init demo --orientation portrait --quality FHD --fps 30
editor.py ingest <project-dir> <source-path>
editor.py analyze <input-video> <analysis-dir> --threshold 0.3 --interval 10
editor.py transcribe <input-media> <output-stem> --model base --language pt
editor.py remove-bg <input-image> <output.png> --model u2netp
editor.py remove-bg <input-video> <output.mov> --video --model u2netp --fps 30
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
node render.mjs <project> --preview
node render.mjs <project>
```

The motion renderer initializes a usable scene if missing. Edit `<project>/motion/<asset-id>/scene.tsx` and its project module, rerun, and reference the resulting PNG sequence as a `frames` clip. Options for orientation/resolution are explicit; do not silently mismatch the timeline. Cached identical renders are reused. Remotion preview uses half scale; final uses the exact manifest dimensions. Optional `--output <path>` changes the export destination. A timestamped name avoids overwriting prior exports.
