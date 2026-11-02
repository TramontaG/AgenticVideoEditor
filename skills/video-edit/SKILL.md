---
name: video-edit
description: Edit and assemble videos through the agent using FFmpeg, Motion Canvas animations, and a persistent Remotion timeline. Handles supplied media, transcription, subtitles, background removal, reusable workflows, style profiles, previews, and exports. Use for video editing and revisions; excludes generative video and building a full graphical editor.
---

# Agent video editing

Deliver an editable project and a checked video. Work locally by default. Match the user's brief, language, media, and established permissions; make routine editing decisions autonomously. Do not require approval for every creative step. Ask only for consequential missing information or decisions the user reserves.

## Brief and visual direction

Before starting a new video, ask whether the output should be portrait or landscape, unless the user has already chosen the orientation in the request or current conversation. Do not silently accept the command-line landscape default. Keep the chosen orientation for revisions unless the user changes it.

Use rounded, casual fonts as the default visual direction, adapting them to the user's instructions, brand, subject, and readability needs. Prioritize images, footage, diagrams, and visual action; keep on-screen text brief and purposeful. Avoid a sequence of static title cards or text-heavy slides unless the user requests that format. Let movement and transformations carry the explanation where appropriate.

## Portable environment

This skill is shared, not a particular user's workspace. Never embed a person's paths, credentials, GPU, language, or aesthetic into its instructions or templates. `AI_EDITOR_ROOT`, the user's configuration, or `setup.py --root` selects the runtime. Preferences, models, projects, credentials, and installation reports live there, outside the skill.

Before first use or after an environment failure, run `python scripts/setup.py doctor`. To install, run `python scripts/setup.py install --root <chosen-directory> --download-models`. Use a Python 3.11–3.13 interpreter. Read [installation.md](references/installation.md) for OS bootstrap, permissions, hardware, and recovery. Diagnose missing tools and install them with the supported OS package manager using `--install-system` when authorized. Do not change GPU drivers automatically. CPU is a supported fallback. Never describe a dependency as tested until its smoke test succeeds.

## Editing workflow

1. Resolve or create a project with `scripts/editor.py init <slug>`. Use the confirmed orientation explicitly. Other defaults are FHD, 30 FPS, and H.264 MP4. Preserve source FPS where appropriate. HD/FHD/QHD and both orientations are supported. Read the manifest, project decisions, and selected style before revising an existing project.
2. Ingest supplied media using `ingest`. It copies and hashes sources, leaving originals untouched. Use `analyze` for FFprobe metadata, FFmpeg scene boundaries, silence intervals, and timestamped reference frames. Inspect the actual frames and listen/read transcription to interpret content; scene detection alone does not identify meaning. Use `transcribe` for timed words, segments, JSON, and SRT. For an actual silence-cut video, use `scripts/remove_video_silence.py`; keep its JSON cut map for subtitle timing. For video cutouts, use `scripts/remove_video_background.py`, which defaults to transparent WebM with audio and streams frames without PNG files. When combining these operations, cut silence first to avoid model inference on discarded footage. Do not infer scene content from filenames alone.
3. To use a website as visual evidence or a background asset, run `scripts/capture_page.py <project> <asset-id> <url>` with full-page, viewport, or selector options from [commands.md](references/commands.md). Keep capture provenance and inspect the resulting image. Use the returned image clip descriptor when composing the timeline. Plan framing, pacing, crops, zooms, sound, and subtitles from the brief and evidence. Explicit user instructions take precedence. Write stable clip/asset IDs, source offsets, timing in frames, and decisions into project files. Resolve timing against one master FPS. Read [project-format.md](references/project-format.md) for the timeline and incremental updates.
4. Motion Canvas creates animation, diagrams, charts, and animated graphic assets. Store source and rendered outputs separately under the project's `motion/` and `public/motion/`. Use the installed `tools/motion-render.mjs`; export a transparent VP9 WebM by default. Frames stream directly to FFmpeg without a PNG sequence on disk; use `--format png` only when individual frames are needed. Use the returned `render.json` clip descriptor in the timeline, with `transparent: true` for video assets. Remotion assembles the complete timeline, media, audio, captions, and transitions. Never modify either library's source or `node_modules`. Write original compositions in the independent toolchain or project.
5. Reuse the installed helpers in [commands.md](references/commands.md). Save genuinely reusable workflows as parameterized scripts under runtime `workflows/`, recording inputs, outputs, dependencies, and usage there. Do not promote one project's script to a universal rule. Read [processing.md](references/processing.md) for background removal, silence edits, audio, and media normalization.
6. Before rendering the complete animation or final video, generate and visually inspect previews of every composition. For animated compositions, include entry, middle, exit, transitions, and moments with significant movement or overlap. Check framing, text safe areas, containment within windows or other intended containers, and layer order: foreground tools must remain visible above the elements they act on. Use still renders or short previews from the actual composition code; a coarse contact sheet alone is insufficient when it hides these details. Correct problems and inspect the affected previews again before proceeding. Record the reviewed times and composition revision in `analysis/`.
7. Render the requested final export with `tools/render.mjs`. Check metadata, beginning/middle/end and edited boundaries, audio sync, crop, text safe areas, caption timing, and black/frozen frames. Confirm that the exported video matches the reviewed compositions. The checker provides machine diagnostics, not a substitute for viewing and listening. Deliver links to the final video and project; report material limitations honestly.

## Delivery folder

Copy accepted final videos to the user's preferred delivery folder. Reuse an explicitly chosen folder from the conversation or saved user configuration without asking again. If no preference is known, ask whether they want the suggested default `~/Videos/Chat-Generated` (or its platform equivalent) or another folder; record their choice in user configuration outside this skill. Create the chosen folder if needed, preserve existing videos by using distinct versioned filenames, and verify the copy before reporting its location. Keep the project and working assets in the project directory unless the user also requests those in the delivery folder.

## Revisions and style memory

Keep `project.json`, `timeline/manifest.json`, `timeline/history/`, `analysis/`, and `decisions.json` current. Preserve old timeline revisions before edits. Content hashes and Motion Canvas render fingerprints enable reuse; final assembly may still need rendering. A portrait version needs reframing, not simply stretching.

Store named style profiles under runtime `styles/`: typography, palette, pacing, transitions, caption conventions, audio preferences, approved references, and feedback evidence. Treat inferred preferences as provisional. Distinguish project-specific feedback from a persistent preference, respect user corrections, and support multiple profiles. Do not claim model training or memory beyond these files.

## Stock assets and credentials

Use Pexels only when useful. Every inclusion needs explicit user authorization unless an existing recorded grant covers that inclusion. Read [pexels.md](references/pexels.md). Search/preview candidates, show the proposed selection, then download using `editor.py pexels-download` with the user's authorization quote or a covering grant. Record provenance and scope. Approval to search is not approval to include. Do not post or publish the video unless asked.

Store API keys through `pexels-key` (interactive hidden input) or an existing secret manager; never request a key in chat, print it, put it in a timeline, or commit it. Credentials are user-specific and excluded from project exports. Do not upload private media to cloud services without authorization. Keep model and asset source/license information; consult current upstream licensing if the user's use case requires it.

## Completion criteria

A usable installation has a saved environment report, pinned Node and Python dependency versions, loaded local model weights, a rendered Motion Canvas asset, a Remotion export consuming that asset, and FFprobe validation. Report OS paths and validated hardware as properties of this installation, not universal requirements. If something is blocked, complete independent work, preserve logs, and state exactly what remains.
