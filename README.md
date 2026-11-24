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

## Qualitative Comparison

Eight scenes appear in this order: Green Room, Staircase, DTU 114, DTU 23,
Garden, Pyramid, Valley, and Rubble. Select scenes from the single-row thumbnail
strip using its horizontal scrollbar, touch scrolling, or keyboard focus.
Counter, ScanNet++, Stadium, and 7Scenes Office are omitted from this comparison.

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

Five scenes appear in this order: DTU scan114, Staircase, Green Room, Pyramid, and Stadium.
DTU scan114 is selected initially. Colored Mesh, Surface, and Normals use synchronized
cameras and white backgrounds. Selecting a scene restores its starting viewpoint. There are no scene
counts, Reset view buttons, or Save figure buttons in this section.

Meshes are capped at 500,000 triangles. Green Room and Pyramid use full VSurf
predictions, Poisson depth 10, and remove the lowest 2% density vertices.
Stadium, scan114, and Staircase are copied from `demo_video/assets/`:

- Stadium: bottleneck resolution 128, output resolution 2048, 2M sampled points,
  Poisson depth 10, lowest 3% density vertices removed.
- scan114: 100k sampled points, Poisson depth 9, lowest 3% removed.
- Staircase: full VSurf prediction, Poisson depth 10, lowest 1% removed.

PLY positions and normals are float32, colors uint8, and triangle indices uint32.
Metadata retains settings and hashes. Mesh assets are packaged within `demo/`.

Stadium remains in this section, so its input manifest and thumbnail are retained;
its comparison point clouds are omitted. ScanNet++ is omitted from both sections.

## Regeneration and checks

Comparison generation and validation default to the eight included scenes:

```bash
python -m demo.generate
python -m demo.validate
python -m demo.reconstruct_mesh --reuse-points --output-root outputs/demo_mesh/assets
```

Run inference/reconstruction in the `mesh3r` environment on an allocation. Use
`--scenes` to select scenes and `--output-root` to stage generation. Mesh generation
defaults to Green Room, Pyramid, and the original Stadium configuration.
For the updated Stadium, scan114, and Staircase meshes, use
`python -m demo_video.reconstruct_mesh --scene <scene>` instead. Copy validated `mesh.ply` and
`metadata.json` into `demo/assets/mesh/<scene>/`. The complete model, sampling,
alignment, and coloring conventions are documented in `demo_full/README.md`.

```bash
node tests/test_demo_viewer.mjs
node tests/test_demo_pipeline.mjs
node tests/test_demo_mesh.mjs
node tests/test_demo_variants.mjs
```

The complete version has corresponding `test_demo_full_*.mjs` checks. Both folders
are self-contained; neither requires the other to serve its browser UI.
