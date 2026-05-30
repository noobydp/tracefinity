<p align="center">
  <img src="logo.svg" alt="Tracefinity">
</p>

<p align="center">
  <a href="https://github.com/tracefinity/tracefinity/releases"><img src="https://img.shields.io/github/v/release/tracefinity/tracefinity?style=flat-square&color=6366f1" alt="Release"></a>
  <a href="https://github.com/tracefinity/tracefinity/actions"><img src="https://img.shields.io/github/actions/workflow/status/tracefinity/tracefinity/docker-dev.yml?style=flat-square&label=build" alt="Build"></a>
  <a href="https://github.com/tracefinity/tracefinity/pkgs/container/tracefinity"><img src="https://img.shields.io/badge/ghcr.io-tracefinity-a855f7?style=flat-square" alt="Container"></a>
  <a href="https://github.com/tracefinity/tracefinity/blob/main/LICENSE"><img src="https://img.shields.io/github/license/tracefinity/tracefinity?style=flat-square&color=ec4899" alt="Licence"></a>
</p>

<p align="center">Generate custom <a href="https://gridfinity.xyz/">gridfinity</a> bins from photos of your tools.</p>

## How It Works

1. Place tools on A4/Letter paper (tools can overflow the edges)
2. Take a photo from above
3. Upload and adjust paper corners for scale calibration
4. AI traces tool outlines automatically
5. Save traced tools to your library
6. Group tools into projects when planning a drawer or workspace
7. Create bins from project tools, arrange the layout
8. Download STL/3MF for 3D printing

| Dashboard | Tool Editor | Bin Editor |
|-|-|-|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Tool Editor](docs/screenshots/tool-editor.png) | ![Bin Editor](docs/screenshots/bin-editor.png) |

## Quick Start

Try it at [tracefinity.net](https://tracefinity.net) without installing anything, or self-host:

### Docker

```bash
# local model (no API key needed)
docker run -p 3000:3000 -v ./data:/app/storage ghcr.io/tracefinity/tracefinity

# or with Gemini API
docker run -p 3000:3000 -v ./data:/app/storage -e GOOGLE_API_KEY=your-key ghcr.io/tracefinity/tracefinity
```

Open http://localhost:3000

By default, Tracefinity uses [IS-Net](https://github.com/xuebinqin/DIS) for local tracing -- no API key needed. Set `GOOGLE_API_KEY` to use Gemini instead. See [Tracing Modes](#tracing-modes) for RAM requirements per model.

| Variable | Default | Description |
|-|-|-|
| `GOOGLE_API_KEY` | | Gemini API key. Uses Gemini instead of local models |
| `TRACERS` | auto-detected | Comma-separated list of available tracers, e.g. `gemini,birefnet-lite,isnet` |
| `TRACEFINITY_ONNX_PROVIDER` | `auto` | Local ONNX provider: `auto`, `cuda`, or `cpu` |
| `TRACEFINITY_ONNX_GPU_MEM_LIMIT_MB` | `10240` | CUDA memory cap for ONNX Runtime local tracers. Set `0` to disable |
| `TRACEFINITY_ONNX_ARENA_EXTEND_STRATEGY` | `kSameAsRequested` | ONNX CUDA arena growth strategy. Use `kNextPowerOfTwo` for ONNX Runtime's default growth |
| `GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | Gemini model for mask generation (see below) |
| `TOOL_LABEL_PROVIDER` | `none` | Optional automatic tool naming provider. Use `ollama` locally, `hosted` to prefer Gemini/OpenRouter, or `gemini`/`openrouter` explicitly |
| `TOOL_LABEL_MODEL` | `qwen3-vl:2b` | Ollama vision model used when local tool naming is enabled |
| `TOOL_LABEL_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL for local tool naming |
| `TOOL_LABEL_TIMEOUT_SECONDS` | `30` | Per-request timeout for background naming |
| `TOOL_LABEL_MAX_CROP_PX` | `512` | Maximum long edge for each isolated tool crop in the naming contact sheet |
| `TOOL_LABEL_CONTEXT_TOKENS` | `4096` | Ollama context window for naming. Keeps small VLMs from allocating huge KV cache |
| `TOOL_LABEL_MAX_TOKENS` | `256` | Maximum generated tokens for tool-name JSON |
| `TOOL_LABEL_ATTEMPTS` | `2` | Number of attempts before keeping generic fallback names |

### From Source

Prerequisites: Python 3.11+, Node.js 20+

```bash
git clone https://github.com/tracefinity/tracefinity
cd tracefinity

# First time setup
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install
cd ..

# Run (starts backend on :8000 and frontend on :4001)
make dev
```

Open http://localhost:4001

## Tracing Modes

Tracefinity supports three ways to trace tool outlines from photos. All three produce the same output -- black and white mask images that get converted to editable polygons via OpenCV contour extraction.

### Local models (default)

When no API key is configured, Tracefinity runs a local salient object detection model. No API key, no network access, no cost. Model weights download automatically on first trace. Three CPU-friendly models are available by default, selectable via the `TRACERS` env var or the UI dropdown:

| Model | Speed (CPU) | Min RAM | Quality | Notes |
|-|-|-|-|-|
| [IS-Net](https://github.com/xuebinqin/DIS) (default) | ~0.8s | 2GB | Good | Fastest, lowest memory |
| [BiRefNet Lite](https://github.com/ZhengPeng7/BiRefNet) | ~3.6s | 8GB | Best | Handles reflections and shiny surfaces well |
| [InSPyReNet](https://github.com/plemeri/InSPyReNet) | ~2.8s | 6GB | Good | Apple Silicon (MPS) support |

Paper corner detection runs [U2-Net Portable](https://github.com/xuebinqin/U-2-Net) alongside the tracer. RAM figures include both models. All models load at startup.

**Minimum RAM: 2GB** (IS-Net). BiRefNet Lite needs **8GB**.

BiRefNet General is available as an opt-in GPU tracer. For NVIDIA GPU tracing from
source, install the optional GPU requirements after the default backend
requirements, set `TRACERS=birefnet-general,birefnet-lite,isnet`, and set
`TRACEFINITY_ONNX_PROVIDER=cuda` to require CUDA:

```bash
pip install -r backend/requirements.txt -r backend/requirements-gpu.txt
```

This uses ONNX Runtime GPU for the `rembg` models (`isnet`, `birefnet-lite`,
`birefnet-general`) and avoids PyTorch CUDA for those tracers.

GPU tracing caps the ONNX Runtime CUDA arena at `10240` MB by default and uses
`kSameAsRequested` arena growth to avoid high-water VRAM growth after repeated
BiRefNet General inference. Set `TRACEFINITY_ONNX_GPU_MEM_LIMIT_MB=0` to restore
uncapped ONNX Runtime behavior.

See [#21](https://github.com/tracefinity/tracefinity/issues/21) for the benchmark that led to this selection.

### Automatic tool names

Tracefinity can optionally name traced polygons before you save them to the tool library. This keeps the trace page, selection list, and saved tool names in sync through the existing polygon label.

Naming runs in the background after tracing, so the trace page returns immediately with `tool 1`, `tool 2`, etc. The UI updates labels when the background result lands and only replaces still-generic labels.

If you save tools before naming finishes, Tracefinity keeps the labels that were visible when you saved and ignores late naming results for that trace.

Local naming uses Ollama and sends one numbered contact sheet per trace to a vision model. It is disabled by default and falls back to generic names whenever Ollama is unavailable or the returned name is not usable.

```bash
ollama pull qwen3-vl:2b
TOOL_LABEL_PROVIDER=ollama
TOOL_LABEL_MODEL=qwen3-vl:2b
TOOL_LABEL_OLLAMA_URL=http://localhost:11434
```

For a hosted quality path, set `TOOL_LABEL_PROVIDER=hosted` with `GOOGLE_API_KEY` or `OPENROUTER_API_KEY`. `hosted` prefers Gemini when both keys are present; set `TOOL_LABEL_PROVIDER=openrouter` to force OpenRouter.

### Gemini API

Set `GOOGLE_API_KEY` to use Google's Gemini models instead. Higher accuracy overall, especially on complex or reflective tools. To get a key: [Google AI Studio](https://aistudio.google.com/apikey) (free tier available).

| Model | Pros | Cons |
|-|-|-|
| `gemini-3.1-flash-image-preview` (default) | Fast, good mask quality | Preview model |
| `gemini-3-pro-image-preview` | Best mask quality, pixel-accurate alignment | Slower, preview model |
| `gemini-2.5-flash-image` | Faster, cheaper, GA | Returns arbitrary dimensions, needs post-hoc alignment |

### Manual mask upload

No API key and prefer not to use the local model? Upload a mask manually:

1. Upload your photo and set paper corners
2. Click "Manual" and download the corrected image
3. Open [Gemini](https://gemini.google.com) and paste the image with the provided prompt
4. Download the generated mask (black tools on white background)
5. Upload the mask back to Tracefinity

## Features

- **AI-powered tracing** -- Local model or Gemini generates accurate tool silhouettes from photos
- **Manual mask upload** -- Use the Gemini web interface without an API key
- **Selective saving** -- Choose which traced outlines to keep before saving to your library
- **Tool library** -- Save traced tools and reuse them across multiple bins
- **Bin projects** -- Plan a group of tools and bins together, track which tools still need bins, and create project-scoped bins
- **Tool editor** -- Rotate tools, add/remove vertices, adjust outlines, snap to grid
- **Smooth or accurate** -- Toggle Chaikin subdivision for smooth curves, or keep the raw trace; SVG and STL exports both respect this
- **Finger holes** -- Circular, square, or rectangular cutouts for easy tool removal
- **Interior rings** -- Hollow tools (e.g. spanners) traced correctly with holes preserved
- **Bin builder** -- Drag and arrange tools with snap-to-grid, auto-sizing to fit the gridfinity grid
- **Cutout clearance** -- Configurable tolerance so tools fit without being too loose
- **Cutout chamfer** -- Bevelled top edges on tool pockets for easy tool insertion
- **Contrast insert** -- Generate a separate STL for printing tool silhouettes in a different colour
- **Text labels** -- Recessed or embossed text on bins
- **Gridfinity compatible** -- Proper base profile, magnet holes, stacking lip
- **Live 3D preview** -- See your bin in three.js before printing
- **STL and 3MF export** -- 3MF supports multi-colour printing for embossed text
- **SVG export** -- Individual tool outlines as SVG, with smoothing applied
- **Bed splitting** -- Large bins auto-split into printable pieces with diagonal fit detection
- **Landscape and portrait** -- Paper orientation auto-detected from corner positions
- **Single-container Docker** -- Frontend and backend in one image, data in a single volume

## What is Gridfinity?

[Gridfinity](https://gridfinity.xyz/) is a modular storage system designed by [Zack Freedman](https://www.youtube.com/watch?v=ra_9zU-mnl8). Bins snap into baseplates on a 42mm grid, making it easy to organise tools, components, and supplies. The system is open source and hugely popular in the 3D printing community.

## Licence

MIT
