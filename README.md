# VSurf demo

This is the reduced, standalone presentation. The complete version is preserved
in `demo_full/`, including its original scenes and per-viewer export buttons.

From the repository root:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory demo
```

Open <http://localhost:8000>, forwarding the port if needed. Copy the entire `demo/`
folder to deploy it elsewhere; browser scripts, Three.js, and assets are local.
Use HTTP/HTTPS rather than opening `index.html` through `file://`.

## File layout

```text
demo/
├── index.html          # Page entry point
├── css/style.css       # Page styles
├── js/                 # Comparison, pipeline, and mesh viewers
│   └── lib/            # Shared browser rendering and asset helpers
├── assets/
│   ├── images/         # Framework figure and VSurf icon
│   ├── media/          # Demonstration video
│   ├── mesh/           # Reconstructed meshes by scene
│   ├── pipeline/       # Method-preview geometry
│   └── <scene>/        # Comparison points, thumbnails, and metadata
├── scripts/            # Offline Python generation and validation tools
└── vendor/             # Bundled Three.js runtime and license
```

Serve `demo/` as before. Browser assets are local; `scripts/` is only needed
to regenerate or validate data from the repository. Run these tools as modules
from the repository root, for example `python -m demo.scripts.validate`.

## Qualitative Comparison

The point-comparison picker lists Valley, Staircase, ScanNet++ 1ada7a0617, Rubble, Pyramid, Garden, DTU scan23, and DTU scan114 in reverse alphabetical order. Select scenes from the single-row thumbnail
strip using its horizontal scrollbar, touch scrolling, or keyboard focus.
Counter, Stadium, and 7Scenes Office are omitted from this comparison.

The VSurf, VGGT-omega, and Surflo panels share orbit, zoom, and pan controls.
RGB / Normals switches their appearance; Point size and Reset view affect only
this comparison. Each method has 100,000 points. Input manifests, camera alignment,
colors, normals, and provenance are unchanged from the full demo.

## Method preview

The five Counter pipeline stages and their independent controls are unchanged.
They load near the viewport and share synchronized cameras. On narrow screens,
scroll the pipeline row horizontally. PLY positions and normals use float32,
converted from `viewers/pipeline/assets/counter/` without changing point counts,
ordering, or uint8 colors. `assets/pipeline/counter/source.json` records both
original and converted hashes. The Method assets total approximately 15.8 MB;
`demo_full/` retains the original float64 files.

## Mesh Reconstruction

The mesh picker lists scenes alphabetically by label: BlendedMVS 5a3b9731e24cd76dad1a5f1b, Colosseum, DTU scan34, DTU scan75, Hypersim ai_001_001, and N-RGBD Green Room.
Green Room uses the mesh, input cameras, and thumbnail from `demo_full`. Hypersim uses 64 evenly spaced images and bottleneck resolution 128.
Both viewers initially select the first thumbnail in their own picker. Colored Mesh, Surface, and Normals use synchronized
cameras and white backgrounds. Selecting a scene restores the same mesh-centered framing as `demo_full`, using the saved display rotation or the first input camera’s orientation and a 45° vertical field of view. There are no scene
counts, Reset view buttons, or Save figure buttons in this section.

Meshes are capped at 500,000 triangles. The picker displays six thumbnails per row.

Colosseum uses 16 views from the VGGT Colosseum sequence. Regenerate it with `python -m demo.scripts.indoor_mesh --scenes colosseum`.

BlendedMVS `5a3b9731e24cd76dad1a5f1b` uses 100 evenly spaced views from its 394 valid frames, with foreground masks and bottleneck resolution 128. Regenerate it with `python -m demo.scripts.indoor_mesh --scenes 5a3b9731e24cd76dad1a5f1b`.

New Poisson exports use up to five million oriented points.

Scan75 uses all 49 RGB images from its scene directory under `data/bench/vsurf/surface_v3/dtu` with their supplied foreground masks at bottleneck resolution 64 and pruner probability threshold 0.5. Regenerate it with `python -m demo.scripts.indoor_mesh --scenes scan75`.

Scan34 uses the published 100k-point VSurf Final prediction, Poisson depth 10, and 2% density trimming. Regenerate it with `python -m demo.scripts.reconstruct_mesh --scenes scan34 --output-root demo/assets/mesh`.

PLY positions and normals are float32, colors uint8, and triangle indices uint32.
Metadata retains settings and hashes. Mesh assets are packaged within `demo/`.

## Regeneration and checks

Comparison generation and validation default to the eight included scenes:

```bash
python -m demo.scripts.generate
python -m demo.scripts.validate
python -m demo.scripts.reconstruct_mesh --reuse-points --output-root outputs/demo_mesh/assets
```

Run inference/reconstruction in the `mesh3r` environment on an allocation. Use
`--scenes` to select scenes and `--output-root` to stage generation. Mesh generation
defaults to Scan34. Copy validated `mesh.ply` and `metadata.json` into `demo/assets/mesh/<scene>/`. The complete model, sampling,
alignment, and coloring conventions are documented in `demo_full/README.md`.

```bash
node tests/test_demo_viewer.mjs
node tests/test_demo_pipeline.mjs
node tests/test_demo_mesh.mjs
node tests/test_demo_variants.mjs
```

The complete version has corresponding `test_demo_full_*.mjs` checks. Both folders
are self-contained; neither requires the other to serve its browser UI.
