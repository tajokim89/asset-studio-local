# Asset Studio Local

A local browser-based AI image asset editor prototype.

Current milestone: **Phase 9 AI Chat selected-region edit bridge**.

## Features in current build

- Fabric.js canvas editor
- Left tool rail and per-tool options
- Resizable left/right side panels
- Upload image assets
- Add text and basic shapes
- Drawing layers with brush/pencil/eraser strokes
- Layer panel:
  - starts with `Drawing Layer 1`
  - add drawing/image layers
  - rename layers
  - show/hide and lock
  - reorder with buttons or drag-and-drop
- Checkerboard transparent-background view
- Zoom/Fit controls
- PNG export and JSON project save/load
- Basic color-key background removal
- One-click Remove BG creates a transparent cutout layer while preserving/hiding the original
- AI image generation API stub through local Hermes image provider
- Region selection tools with copy/cut/paste, transparent region PNG export, and AI edit bridge
- AI Chat command router for editor actions and selected-region edit preparation

## Run locally

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start the local server:

```bash
python3 server.py
```

Then open:

```text
http://127.0.0.1:4184
```

## Optional AI generation

`server.py` can call a local Hermes image provider. If your Hermes checkout is not at the default path, set:

```bash
export HERMES_REPO=/path/to/hermes-agent
python3 server.py
```

Without the local Hermes provider, the static editor UI still runs, but `/api/generate` will fail.

## Project notes

See:

- `PHASE_0_BASELINE.md`
- `PHASE_1_REPORT.md`

## Roadmap

Next planned phase:

**Phase 10 — AI Chat multi-step plan polish or inpaint preview/apply UX polish**
