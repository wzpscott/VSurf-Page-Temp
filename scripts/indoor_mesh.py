"""Build the DTU, BlendedMVS, Hypersim, and Colosseum meshes."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from bench.io import digest
from demo.scripts.generate import save_thumbnail, wild_inputs
from demo.scripts.reconstruct_mesh import ROOT, write_mesh_float32, validate_mesh
from viewers.largescale.generate import bottleneck_grid, enable_chunked_mlps
from vsurf_final.inference import POISSON_MAX_POINTS, VSurf, _poisson_mesh
from vsurf_final.frontends.vggt_omega.utils.load_fn import load_and_preprocess_images_with_masks


BMVS = ('5a3b9731e24cd76dad1a5f1b',)
SCENES = ('scan75', 'ai_001_001', 'colosseum', *BMVS)


def inputs_for_scene(name):
    if name == 'colosseum':
        frames = wild_inputs(name)['frames']
        return [Path(f['path']) for f in frames], frames
    count = 64
    if name == 'scan75':
        folder = ROOT/'data/bench/vsurf/surface_v3/dtu'/name
        manifest = json.loads((folder/'transforms.json').read_text())
        frames, paths = [], []
        for frame in manifest['frames']:
            path = folder/frame['file_path']
            mask = folder/frame['mask_path']
            paths.append(path)
            frames.append(dict(path=str(path.relative_to(ROOT)), sha256=digest(path),
                               mask_path=str(mask.relative_to(ROOT)), mask_sha256=digest(mask)))
        return paths, frames
    elif name in BMVS:
        folder = ROOT/'data/geometry/bmvs/blendedmvs'/name
        manifest = json.loads((folder/'valid_frames.json').read_text())
        available = [folder/frame['image_path'] for frame in manifest['frames']]
        count = min(100, len(available))
        paths = [available[i] for i in np.linspace(0, len(available)-1, count, dtype=int)]
        frames = []
        for path in paths:
            masked = path.with_name(path.stem + '_masked.jpg')
            frames.append(dict(path=str(path.relative_to(ROOT)), sha256=digest(path),
                               mask_path=str(masked.relative_to(ROOT)), mask_sha256=digest(masked)))
        return paths, frames
    elif name == 'ai_001_001':
        folder = ROOT/'data/geometry/ml-hypersim/data'/name/'images/scene_cam_00_final_preview'
        available = sorted(folder.glob('frame.*.color.jpg'))
    else:
        raise ValueError(f'Unknown scene: {name}')
    if len(set(available)) < count:
        raise ValueError(f'{name} requires {count} distinct input frames')
    paths = [available[i] for i in np.linspace(0, len(available)-1, count, dtype=int)]
    return paths, [dict(path=str(p.relative_to(ROOT)), sha256=digest(p)) for p in paths]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes', nargs='+', choices=SCENES, default=SCENES)
    args = parser.parse_args()
    model = VSurf.from_checkpoint()
    enable_chunked_mlps(model.model)
    checkpoint_threshold = model.model.fp_pruner.pruning_threshold
    for name in args.scenes:
        paths, frames = inputs_for_scene(name)
        masks = [None] * len(paths)
        for i, frame in enumerate(frames):
            if 'mask_path' in frame:
                with Image.open(ROOT/frame['mask_path']) as image:
                    if name in BMVS:
                        masks[i] = np.asarray(image.convert('RGB')).max(axis=2) > 8
                    else:
                        masks[i] = np.asarray(image.convert('L')) > 0
        rgb, mask = load_and_preprocess_images_with_masks(paths, masks, image_resolution=512, patch_size=16)
        print(f'{name}: predicting from {len(paths)} views', flush=True)
        resolution = 64 if name in ('colosseum', 'scan75') else 128
        threshold = 0.5 if name == 'scan75' else checkpoint_threshold
        model.model.fp_pruner.set_pruning_threshold(threshold)
        with bottleneck_grid(model.model, resolution) as grid:
            result = model.reconstruct(rgb, mask=mask)
        points = {k:result[k].detach().cpu() for k in ('points','colors','normals')}
        poses = result['extrinsics'].detach().cpu().numpy()
        del result
        mesh = _poisson_mesh(points, depth=10, seed=42)
        assets = ROOT/'demo/assets'
        folder = assets/'mesh'/name
        folder.mkdir(exist_ok=True, parents=True)
        write_mesh_float32(folder/'mesh.ply', mesh)
        validate_mesh(mesh)
        for frame, pose in zip(frames, poses):
            matrix = np.eye(4)
            matrix[:3] = pose[:3]
            frame['c2w'] = np.linalg.inv(matrix).tolist()
        scene = dict(scene=name, input_frames=len(paths), frames=frames, camera_source='vsurf_predicted_opencv_c2w')
        inputs = assets/name
        inputs.mkdir(exist_ok=True)
        (inputs/'inputs.json').write_text(json.dumps(scene, indent=2)+'\n')
        save_thumbnail(name, scene, inputs)
        metadata = dict(**grid, scene=name, fp_pruner_threshold=threshold, method='screened_poisson', depth=10, density_quantile=.02, max_triangles=500000,
                        position_dtype='float32', normal_dtype='float32', vertices=len(mesh.vertices),
                        triangles=len(mesh.triangles), input_frames=len(paths), max_input_points=POISSON_MAX_POINTS,
                        raw_points=len(points['points']), inputs_sha256=digest(inputs/'inputs.json'),
                        ply_sha256=digest(folder/'mesh.ply'))
        (folder/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')


if __name__ == '__main__':
    main()
