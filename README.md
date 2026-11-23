# VSurf demo

Serve this directory with any static HTTP server:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory demo
```

Open <http://localhost:8000>. Forward port 8000 if running remotely. The complete
`demo/` directory can be copied to another host; no CDN, model server, repository
imports, or network assets are required by the browser. Open the page through
HTTP or HTTPS; opening `index.html` directly through `file://` does not load the
3D scenes. A notice at the top of the page provides local-server instructions.

Keyboard and mouse controls use the same OrbitControls defaults as the viewers:
left-drag to orbit; scroll, middle-drag, or pinch to zoom; right-drag or
Ctrl/⌘/Shift + left-drag to pan. Scroll outside the viewers to move the page.
The three 4:3 viewers show VSurf, VGGT-omega, and Surflo from left to right,
with synchronized cameras. Use RGB / Normals to switch all panels, and click
the thumbnail buttons to change scenes. Reset
returns to a centered view at 62.5% of the distance needed to fit the scene
bounds. Normal colors are camera-relative. The view keeps the first
reference or predicted camera's orientation (the bench viewer's display orientation
for DTU and Office) and uses the same orbit controls as the Wild viewer.
The orbit target is the center of the VSurf and VGGT-omega bounds.

## Method preview

The Method section includes five synchronized Counter pipeline stages, loaded
when the section approaches the viewport. Its point-size and reset controls are
independent of the comparison below. On narrow screens, scroll the stage row
horizontally. Pruned features use the pipeline viewer's perceptual PCA palette
and 90% voxel fill; input and output use world-space framing while the two
intermediate stages use contracted framing.

These assets are exact copies of `viewers/pipeline/assets/counter/`, bundled in
`assets/pipeline/counter/`. `source.json` records their source and SHA-256 hashes.
The RGB and normals output panels share one PLY. Only the four displayed clouds
are included; the legacy encoder export is unused. Rendering helpers under
`lib/pipeline/` are adapted from the pipeline viewer. Verify the integration with
`node tests/test_demo_pipeline.mjs` from the repository root.

## Regenerate

From the repository root, in the `mesh3r` environment on an allocated CUDA GPU:

```bash
python -m demo.generate
python -m demo.validate
```

Optional `--scenes counter garden pyramid valley stadium rubble` and
`--methods vsurf_final vggt_omega surflo_plain` restrict generation. Validation
also accepts `--scenes`. Generation overwrites the selected assets. Do not regenerate
while serving a public copy; generate and validate first, then copy the directory.
To stage assets separately, pass `--output-root outputs/demo_16frames_200k/assets` to
generation and `--asset-root outputs/demo_16frames_200k/assets` to validation.
Additional scene IDs are `green_room`, `staircase`, `1ada7a0617`,
`scan114`, `scan23`, and `office`. To regenerate just those scenes, pass them to `--scenes`
and stage them under a separate `--output-root` before validation and installation.

All methods use the same input frames. Counter and Garden use 16 uniformly
spaced, naturally sorted `images_4` files. Pyramid uses 16 uniformly spaced
entries from the Wild viewer's frozen input manifest. Valley uses all 11
available images. Stadium uses 128 uniformly sampled frames out of 429 from BlendedMVS scene
`5afacb69ab00705d0cefdd5b`.
Rubble uses the same 256 `images_8` inputs as the largescale viewer.
The two NRGBD scenes and the ScanNet++ scene use the bench viewer's exact
100-frame selections; the DTU scenes use its exact 49-frame selections.
The NRGBD and ScanNet++ scenes are freshly inferred with the demo pipeline.
The two DTU scenes copy the bench viewer's published PLY files byte-for-byte
for all three methods, preserving their colors, normals, foreground masking,
and original alignment. `python -m demo.generate --scenes scan114 scan23`
refreshes these copies without GPU inference.
7Scenes Office uses freshly inferred VSurf results and the bench viewer's exact
Omega and Surflo PLYs, with the bench display orientation, 100 input frames, and
100,000 points per method. VSurf uses camera Sim3 alignment without ICP. Refresh it with
`python -m demo.generate --scenes office`.
VSurf uses `vsurf_final`, its final checkpoint, median-point-radius
normalization, and no TTO. Omega uses the existing 1B checkpoint. Surflo uses its
released EMA checkpoint and plain unguided flow with 100 steps and 200k queries.
VSurf uses projected image RGB; Omega uses pixel RGB. Surflo copies RGB from
the nearest point in its own original VGGT cloud, using that point's input-pixel
color. Run `python -m demo.recolor --output-root outputs/demo_vggt_colors/assets`
to stage updated Surflo colors without changing existing geometry. Counter, Garden,
and Stadium use reference cameras only for display alignment via seeded camera
Sim3, without ICP. Pyramid, Valley, and Rubble use the shared native Omega frame; Surflo
is aligned to Omega's predicted cameras using the same camera Sim3 procedure.

The imported DTU clouds retain the bench viewer's dataset foreground masking.
Importing applies no additional filtering, resampling, or recoloring. The color
refresh command also preserves these exact copies. Validation checks each copy
against its source PLY hash, and per-method metadata retains bench provenance.

All comparison scenes store 100,000 points per method. The original six scenes
were subsampled from their 200,000-point exports without replacement using
NumPy default_rng with seed 42, preserving source order and all point attributes.
Per-method `post_export_sampling` metadata records the original PLY hash and
sampling procedure; `prediction_sampling` retains the original export settings. Each PLY stores float32 XYZ and unit normals
and uint8 RGB.
Sampling uses seed 42 without replacement. `assets/<scene>/inputs.json` records
input selections and cameras; per-method JSON records checkpoint identities,
inference settings, alignment, and hashes. Thumbnails use the middle selected
input (index `input_frames // 2`), except the benchmark additions, whose input
indices are fixed in `THUMBNAIL_FRAMES`, and Stadium, which uses source frame 372
for a full view of the seating bowl and field. Python generation requires repository code and datasets;
the completed browser demo does not.

Three.js and its MIT license are bundled under `vendor/three/`. Rendering utilities
are local copies adapted from the repository viewers.
