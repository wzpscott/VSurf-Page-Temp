"""Recolor existing Surflo PLYs from original VGGT RGB without changing geometry."""
import argparse
import gc
import json
from pathlib import Path

import numpy as np

from demo.scripts.generate import ROOT, DEST, SCENES, PlainSurflo
from demo.scripts.coloring import original_vggt_colors
from viewers.bench.ply import VERTEX
from bench.io import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    import torch
    model = PlainSurflo()
    from surflo.api import set_global_seeds
    from demo.scripts.foreground import load_masks, surflo_masks
    for scene in SCENES:
        print(f'{scene}: encoding original VGGT colors', flush=True)
        folder = DEST/scene
        inputs = json.loads((folder/'inputs.json').read_text())
        if json.loads((folder/'surflo_plain.json').read_text()).get('asset_source') == 'bench_viewer_ply':
            print(f'{scene}: keeping exact bench viewer colors', flush=True)
            continue
        paths = [str(ROOT/frame['path']) for frame in inputs['frames']]
        for frame, path in zip(inputs['frames'], paths):
            if digest(Path(path)) != frame['sha256']:
                raise ValueError(f'{scene}: input image changed')
        record = json.loads((folder/'surflo_plain.json').read_text())
        ply = folder/'surflo_plain.ply'
        if digest(ply) != record['ply_sha256']:
            raise ValueError(f'{scene}: Surflo PLY does not match its provenance')
        with ply.open('rb') as stream:
            header = []
            while True:
                line = stream.readline()
                if not line:
                    raise ValueError('Incomplete PLY header')
                header.append(line)
                if line == b'end_header\n':
                    break
            vertices = np.frombuffer(stream.read(), dtype=VERTEX).copy()
        points = np.column_stack([vertices[key] for key in ('x', 'y', 'z')])
        alignment = record['alignment']
        # Reverse display Sim3 to query the original VGGT cloud in Surflo's frame.
        points = ((points - np.asarray(alignment['translation'])) @ np.asarray(alignment['rotation'])) / alignment['scale']
        set_global_seeds(42)
        with torch.no_grad():
            state = model.model.encode(paths, target_size=518, cull_radius=10.)
        masks = load_masks(inputs)
        valid_mask = surflo_masks(paths, masks, state.images) if masks is not None else None
        colors, coloring = original_vggt_colors(state, paths, points, valid_mask=valid_mask)
        for index, key in enumerate(('red', 'green', 'blue')):
            vertices[key] = np.rint(colors[:, index] * 255).astype(np.uint8)
        output = args.output_root/scene
        output.mkdir(parents=True, exist_ok=True)
        target = output/'surflo_plain.ply'
        with target.open('wb') as stream:
            stream.write(b''.join(header))
            vertices.tofile(stream)
        record.update(coloring=coloring, ply_sha256=digest(target))
        (output/'surflo_plain.json').write_text(json.dumps(record, indent=2)+'\n')
        print(f'{scene}: recolored {len(vertices)} points; geometry preserved', flush=True)
        del state
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == '__main__':
    main()
