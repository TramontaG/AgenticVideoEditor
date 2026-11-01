---
name: video-edit
description: Edit and assemble videos through the agent using FFmpeg, Motion Canvas animations, and a persistent Remotion timeline. Handles supplied media, transcription, subtitles, background removal, reusable workflows, style profiles, previews, and exports. Use for video editing and revisions; excludes generative video and building a full graphical editor.
---

# Agent video editing

Deliver an editable project and a checked video. Work locally by default. Match the user's brief, language, media, and established permissions; make routine editing decisions autonomously. Do not require approval for every creative step. Ask only for consequential missing information or decisions the user reserves.

## Portable environment

This skill is shared, not a particular user's workspace. Never embed a person's paths, credentials, GPU, language, or aesthetic into its instructions or templates. `AI_EDITOR_ROOT`, the user's configuration, or `setup.py --root` selects the runtime. Preferences, models, projects, credentials, and installation reports live there, outside the skill.

Before first use or after an environment failure, run `python scripts/setup.py doctor`. To install, run `python scripts/setup.py install --root <chosen-directory> --download-models`. Use a Python 3.11–3.13 interpreter. Read [installation.md](references/installation.md) for OS bootstrap, permissions, hardware, and recovery. Diagnose missing tools and install them with the supported OS package manager using `--install-system` when authorized. Do not change GPU drivers automatically. CPU is a supported fallback. Never describe a dependency as tested until its smoke test succeeds.

## Editing workflow

1. Resolve or create a project with `scripts/editor.py init <slug>`. Defaults are FHD, 30 FPS, landscape, H.264 MP4; use portrait for a portrait destination or explicit request. Preserve source FPS where appropriate. HD/FHD/QHD and both orientations are supported. Read the manifest, project decisions, and selected style before revising an existing project.
2. Ingest supplied media using `ingest`. It copies and hashes sources, leaving originals untouched. Use `analyze` for FFprobe metadata, FFmpeg scene boundaries, silence intervals, and timestamped reference frames. Inspect the actual frames and listen/read transcription to interpret content; scene detection alone does not identify meaning. Use `transcribe` for timed words, segments, JSON, and SRT. Do not infer scene content from filenames alone.
3. Plan framing, pacing, crops, zooms, sound, and subtitles from the brief and evidence. Explicit user instructions take precedence. Write stable clip/asset IDs, source offsets, timing in frames, and decisions into project files. Resolve timing against one master FPS. Read [project-format.md](references/project-format.md) for the timeline and incremental updates.
4. Motion Canvas creates animation, diagrams, charts, and animated graphic assets. Store source and rendered outputs separately under the project's `motion/` and `public/motion/`. Use the installed `tools/motion-render.mjs`; preserve alpha with PNG frames or ProRes 4444. Remotion assembles the complete timeline, media, audio, captions, and transitions. Never modify either library's source or `node_modules`. Write original compositions in the independent toolchain or project.
5. Reuse the installed helpers in [commands.md](references/commands.md). Save genuinely reusable workflows as parameterized scripts under runtime `workflows/`, recording inputs, outputs, dependencies, and usage there. Do not promote one project's script to a universal rule. Read [processing.md](references/processing.md) for background removal, silence edits, audio, and media normalization.
6. Render a lightweight preview when helpful, then the requested final export with `tools/render.mjs`. Check metadata, beginning/middle/end and edited boundaries, audio sync, crop, text safe areas, caption timing, and black/frozen frames. The checker provides machine diagnostics, not a substitute for viewing and listening. Use `renderStill`/extracted frames for visual review. Deliver links to the final video and project; report material limitations honestly.

## Revisions and style memory

Keep `project.json`, `timeline/manifest.json`, `timeline/history/`, `analysis/`, and `decisions.json` current. Preserve old timeline revisions before edits. Content hashes and Motion Canvas render fingerprints enable reuse; final assembly may still need rendering. A portrait version needs reframing, not simply stretching.

Store named style profiles under runtime `styles/`: typography, palette, pacing, transitions, caption conventions, audio preferences, approved references, and feedback evidence. Treat inferred preferences as provisional. Distinguish project-specific feedback from a persistent preference, respect user corrections, and support multiple profiles. Do not claim model training or memory beyond these files.

## Stock assets and credentials

Use Pexels only when useful. Every inclusion needs explicit user authorization unless an existing recorded grant covers that inclusion. Read [pexels.md](references/pexels.md). Search/preview candidates, show the proposed selection, then download using `editor.py pexels-download` with the user's authorization quote or a covering grant. Record provenance and scope. Approval to search is not approval to include. Do not post or publish the video unless asked.

Store API keys through `pexels-key` (interactive hidden input) or an existing secret manager; never request a key in chat, print it, put it in a timeline, or commit it. Credentials are user-specific and excluded from project exports. Do not upload private media to cloud services without authorization. Keep model and asset source/license information; consult current upstream licensing if the user's use case requires it.

## Completion criteria

A usable installation has a saved environment report, pinned Node and Python dependency versions, loaded local model weights, a rendered Motion Canvas asset, a Remotion export consuming that asset, and FFprobe validation. Report OS paths and validated hardware as properties of this installation, not universal requirements. If something is blocked, complete independent work, preserve logs, and state exactly what remains.
