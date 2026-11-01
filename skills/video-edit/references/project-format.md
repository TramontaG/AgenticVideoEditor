# Project and timeline

Runtime contains `tools/`, `models/`, `projects/`, `styles/`, `workflows/`, `logs/`, and private `config/`. Each project contains:

```
project.json                 project identity, source registry and hashes
decisions.json               editing decisions, style choice, stock authorization
originals/                   immutable working copies of user assets
public/media/                media exposed to Remotion
public/motion/<asset-id>/     rendered animation and render fingerprint
motion/<asset-id>/           editable Motion Canvas source and metadata
timeline/manifest.json       full Remotion timeline
timeline/history/            previous manifest revisions
analysis/<asset-id>/         metadata, cuts, silence, thumbnails, transcripts
exports/                    preview, final video and QA
```

Manifest example (frame values are integers, end is exclusive):

```json
{
  "version": 1,
  "width": 1920, "height": 1080, "fps": 30, "durationInFrames": 150,
  "background": "#111827",
  "clips": [
    {"id":"intro", "type":"title", "from":0, "durationInFrames":60,
     "text":"Title from the project brief", "color":"white", "fontSize":72},
    {"id":"footage-01", "type":"video", "src":"media/shot.mp4",
     "from":60,"durationInFrames":90,"trimStartFrames":30,
     "objectFit":"cover","objectPosition":"50% 35%","volume":1,
     "zoomStart":1,"zoomEnd":1.08,"fadeInFrames":6,"fadeOutFrames":6}
  ]
}
```

Types: `image`, `video`, `audio`, `title`, `frames` (Motion Canvas PNG sequence). Array order determines visual stacking. `from` is the master start; `trimStartFrames` is the media source offset at master FPS. `frames` uses `src` directory, `frameCount`, and `framePattern` default `%06d.png`, starting at zero. The rendered animation must share the timeline FPS and declared duration. Use `x`, `y`, `width`, `height` for inset layers; omitted dimensions fill the canvas. `opacity`, `volume`, `objectFit`, `objectPosition`, zoom and fade controls are supported. Titles accept `fontFamily`, `fontSize`, `color`, `textAlign`.

Subtitles can be title clips with transparent backgrounds and timed segments; convert SRT/word timing to frames only after applying the source-to-edit cut map. Safe-area placement and line breaking are project decisions. For more complex transitions or audio envelopes, extend project-local composition code, keeping timing deterministic and the manifest authoritative.

Never reuse an ID for a different source. Snapshot the manifest before editing. Update dependent durations and timestamps when cuts change. Preserve source-to-output timing maps in analysis for captions and audio. Derive re-render fingerprints from all animation sources, parameters, imported assets and dependency lockfiles; the provided renderer hashes the asset directory and package lock. If sources import files outside that directory, copy them inside or extend the fingerprint. Validate source ranges against probed media, especially after FPS conversion.

For reproducibility retain dependency lockfiles and model IDs/checksums. Cache is disposable; original assets, manifests and animation source are not.
