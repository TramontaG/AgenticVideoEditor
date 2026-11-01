# AI Video Editor Skill

Edit videos through an AI agent using **FFmpeg**, **Motion Canvas**, **Remotion**, and local auxiliary models. Keep animation sources, processed media, and the complete timeline available for later revisions.

This is an agent skill and a reusable local toolchain. It is not a graphical editing suite or a generative video model.

## Install through an agent

Give your agent the GitHub URL of **`skills/video-edit`**, and ask it to install that skill. In Codex, use:

```text
Use $skill-installer to install https://github.com/TramontaG/AgenticVideoEditor/tree/main/skills/video-edit
```

The skill directory includes `SKILL.md`, executable helpers, references, and the independent rendering toolchain. Installing the skill copies those files; the rendering libraries and model weights are installed separately on first setup.

Then ask:

```text
Use $video-edit to check this computer, install the prerequisites in a dedicated
directory, and edit the media I provide. Keep the project editable for later changes.
```

The agent follows the installation instructions, checks the operating system and hardware, and requests system-level permissions only when required by its environment.

Copy-ready examples for setup, editing, revisions, style profiles, animations, and Pexels authorization are in [PROMPTS.md](PROMPTS.md).

## Manual setup

Clone this repository, then run:

```bash
git clone https://github.com/TramontaG/AgenticVideoEditor.git
cd AgenticVideoEditor
python3 skills/video-edit/scripts/setup.py doctor
python3 skills/video-edit/scripts/setup.py install --install-system --download-models
python3 skills/video-edit/scripts/setup.py smoke
```

On Windows, use `py` or `python` instead of `python3`. If Python itself is absent, see [installation and bootstrap instructions](skills/video-edit/references/installation.md).

Choose a runtime directory with `--root /path/to/AI-Editor` or `AI_EDITOR_ROOT`. Otherwise, the installer uses the current user's saved location or `~/Videos/AI-Editor`. Models, projects, preferences, credentials, and installed dependencies stay outside this repository.

Required runtime tools are Node.js 22+, Python 3.11–3.13, FFmpeg/FFprobe, and a compatible headless browser. The installer reuses existing prerequisites, creates an isolated Python environment, and installs Node dependencies locally. It supports apt/dnf/pacman, Homebrew, and winget. A compatible Python can be selected automatically or downloaded privately through uv when authorized. An unsupported package-manager configuration produces a diagnostic rather than silently replacing system Python.

To update bundled tools in an existing runtime, add `--update-toolchain` to the install command. Differing existing files are backed up before replacement.

## What it does

- Analyze video metadata, scene boundaries, reference frames, and silence.
- Transcribe locally with segment and word timestamps, JSON, and SRT output.
- Remove image backgrounds and provide a frame-by-frame video cutout workflow.
- Normalize media, plan edits, or export a video with long silences removed while keeping audio/video synchronized.
- Create animation assets with Motion Canvas and assemble the complete timeline in Remotion.
- Export landscape or portrait video in HD, FHD, and QHD.
- Store animations as transparent VP9 WebM files by default, streaming frames directly to FFmpeg without writing PNG sequences to disk. PNG output remains optional.
- Reuse unchanged animation renders and preserve timeline snapshots.
- Maintain separate, editable style profiles for each user or project.
- Search and download Pexels assets with recorded user authorization.

### Division of responsibilities

```text
User media → FFmpeg analysis / local preprocessing
                          ↓
Motion Canvas → separate animation assets
                          ↓
Remotion → complete timeline → preview / final export
```

The templates import the libraries; they do not modify upstream projects or `node_modules`.

## Dedicated processing scripts

```bash
python3 skills/video-edit/scripts/remove_video_background.py input.mp4 output.webm
python3 skills/video-edit/scripts/remove_video_silence.py input.mp4 edited.mp4 --padding 0.15
```

Background removal preserves real transparency and the primary audio stream, without saving per-frame images. Silence removal produces an edited video and a JSON timing map for subtitles. Both preserve the original and refuse to overwrite existing outputs. For a combined workflow, remove silence before running model inference. See the [command reference](skills/video-edit/references/commands.md) for settings and output formats.

## Project organization

```text
AI-Editor/
├── tools/          Local Node toolchain and Python environment
├── models/         Downloaded model weights
├── styles/         User-specific editing profiles
├── workflows/      Reusable custom workflows
├── config/         Private local configuration
├── logs/           Installation and validation reports
└── projects/
    └── example/
        ├── originals/
        ├── public/media/
        ├── public/motion/
        ├── motion/
        ├── timeline/manifest.json
        ├── timeline/history/
        ├── analysis/
        ├── decisions.json
        └── exports/
```

See the [command reference](skills/video-edit/references/commands.md), [timeline format](skills/video-edit/references/project-format.md), and [processing guidance](skills/video-edit/references/processing.md).

## Local models and stock media

The bootstrap downloads multilingual faster-whisper `base` and rembg `u2netp`. CPU inference is supported; GPU drivers are never replaced automatically. Optional larger or temporal models can be added for particular footage.

Framewise background removal is a baseline: hair, motion blur, and occlusions may require a temporal matting workflow. Validate representative shots before processing a long video.

Pexels is optional. Each inclusion requires the user's authorization unless an existing grant covers it. Keys belong in a secret manager or private local configuration, never in this repository. See [Pexels setup](skills/video-edit/references/pexels.md).

Third-party libraries, model weights, and stock assets retain their own licenses and usage terms. See the upstream links in the installation reference, including Remotion's licensing documentation.

## Validation and platform status

The initial toolchain was tested on Linux x86_64 with CPU inference: scene/silence detection, speech transcription, image/video alpha output, normalization, Motion Canvas → Remotion assembly, cached animation reuse, and FHD/QHD exports including portrait. The installer contains Windows and macOS routes; those full installations have not yet been tested.

Run lightweight checks from the repository root:

```bash
python3 -m unittest discover -s tests -v
node --test tests/animation-output.test.mjs
```

For the end-to-end check, run `setup.py smoke` after installation. It creates a fresh synthetic project, runs the local models, renders an animation, assembles a video, and saves diagnostics. It downloads no stock media and publishes nothing. Visual and audio review remain part of final delivery.

## Repository contents

The shareable skill is entirely inside [`skills/video-edit`](skills/video-edit). Runtime projects, credentials, media, model binaries, and personal configuration are excluded. The repository's checks run on Linux, macOS, and Windows; a separate workflow can run the full Linux integration test on demand.
