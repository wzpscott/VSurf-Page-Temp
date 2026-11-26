"""Generate the standalone demo assets. Run from the repository: python -m demo.scripts.generate."""
import argparse
import gc
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'demo/assets'
METHODS = ('vsurf_final', 'vggt_omega', 'surflo_plain')
BENCH_SCENES = dict(green_room='nrgbd', staircase='nrgbd',
                    **{'1ada7a0617':'scannetpp'},
                    scan114='dtu', scan34='dtu', scan23='dtu', office='7scenes')
SCENES = ('1ada7a0617', 'staircase', 'scan114', 'scan23', 'garden', 'pyramid', 'valley', 'rubble',
          'stadium', 'counter', 'green_room')
WILD_SCENES = dict(colosseum='vggt_videos/colosseum', pyramid='vggt_videos/pyramid', valley='pi3_examples/valley',
                   stadium='blendedmvs/5afacb69ab00705d0cefdd5b')
THUMBNAIL_FRAMES = dict(green_room=0, staircase=99,
                       **{'1ada7a0617':33}, scan114=48, scan23=0)


def save_thumbnail(name, scene, folder):
    from bench.io import digest
    index = THUMBNAIL_FRAMES.get(name, len(scene['frames'])//2)
    path = (ROOT/'data/geometry/bmvs/blendedmvs/5afacb69ab00705d0cefdd5b/blended_images/00000372.jpg'
            if name == 'stadium' else ROOT/scene['frames'][index]['path'])
    with Image.open(path) as im:
        im.thumbnail((640, 480))
        im.convert('RGB').save(folder/'thumbnail.jpg', quality=90)
    (folder/'thumbnail.json').write_text(json.dumps(dict(source=str(path), source_sha256=digest(path),
        thumbnail_sha256=digest(folder/'thumbnail.jpg')), indent=2)+'\n')


def wild_inputs(name):
    from bench.io import digest
    assets = ROOT/'viewers/wild/assets'
    catalog = json.loads((assets/'catalog.json').read_text())
    manifest_path = assets/catalog['manifest_url']
    manifest = json.loads(manifest_path.read_text())
    source = next(scene for scene in manifest['scenes'] if scene['id'] == WILD_SCENES[name])
    count = min(16, len(source['frames']))
    ids = np.linspace(0, len(source['frames'])-1, count, dtype=int)
    frames = []
    for index in ids:
        original = source['frames'][index]
        if digest(Path(original['path'])) != original['sha256']:
            raise ValueError(f'{name}: Wild source image changed')
        frames.append({key: original[key] for key in ('path', 'sha256', 'c2w')})
    return dict(scene=name, source_scene=source['id'], frames=frames, input_frames=count,
                sampling=dict(policy='uniform_linspace_wild_manifest', indices=ids.tolist(),
                              available=len(source['frames'])),
                source_manifest_sha256=digest(manifest_path), seed=42, point_count=100000,
                camera_source=source['camera_source'])


def scene_inputs(name):
    if name in BENCH_SCENES:
        from bench.io import digest, fingerprint
        dataset = BENCH_SCENES[name]
        directory = ROOT/'outputs/bench_viewer_final_100views_782887/data'/dataset/name
        source = json.loads((directory/'transforms.json').read_text())
        report = json.loads((ROOT/f'viewers/bench/assets/metrics/{dataset}.json').read_text())['scenes'][name]
        expected_count = 49 if dataset == 'dtu' else 100
        if len(source['frames']) != expected_count or any(
                report[method]['provenance']['scene'] != fingerprint(source) for method in METHODS):
            raise ValueError(f'{name}: prepared inputs do not match the published bench scene')
        frames = []
        for frame in source['frames']:
            path = directory/frame['file_path']
            item = dict(path=str(path.resolve()), sha256=digest(path), c2w=frame['transform_matrix'],
                        intrinsics=frame['intrinsics'])
            if dataset == 'dtu':
                mask = directory/frame['mask_path']
                item.update(mask_path=str(mask.resolve()), mask_sha256=digest(mask))
            frames.append(item)
        return dict(scene=name, source_scene=f'{dataset}/{name}', frames=frames,
                    input_frames=len(frames), seed=42, point_count=100000, camera_source='opencv_c2w',
                    sampling=dict(policy='exact_bench_selection', indices=list(range(len(frames))), available=len(frames)),
                    source_metadata_sha256=digest(directory/'transforms.json'),
                    foreground_mask_policy='dtu_foreground_only' if dataset == 'dtu' else None)
    if name == 'rubble':
        from bench.io import digest
        metadata_path = ROOT/'viewers/largescale/assets/rubble/metadata.json'
        metadata = json.loads(metadata_path.read_text())
        if len(metadata['images']) != 256:
            raise ValueError('Expected 256 Rubble images from the largescale viewer')
        return dict(scene=name, source_scene='mill19/rubble',
                    frames=[dict(path=path, sha256=digest(Path(path)), c2w=None)
                            for path in metadata['images']],
                    input_frames=256, seed=42, point_count=100000,
                    image_directory='images_8', sampling=metadata['frame_selection'],
                    source_metadata_sha256=digest(metadata_path), camera_source='omega_native')
    if name == 'stadium':
        from viewers.wild.protocol import bmvs_sources, natural_key
        from bench.io import digest
        _, _, candidates, sources, convention = bmvs_sources()[0]
        candidates.sort(key=lambda item: natural_key(item[0].name))
        if len(candidates) < 128:
            raise ValueError('Stadium requires at least 128 available frames')
        indices = np.linspace(0, len(candidates)-1, 128, dtype=int)
        frames = [dict(path=str(path), sha256=digest(path), c2w=pose.tolist())
                  for path, pose in (candidates[index] for index in indices)]
        return dict(scene=name, source_scene=WILD_SCENES[name], frames=frames,
                    input_frames=len(frames), seed=42, point_count=100000,
                    sampling=dict(policy='uniform_linspace_natural_order', indices=indices.tolist(),
                                  available=len(candidates)),
                    source_metadata_sha256=digest(sources[0]), camera_source=convention)
    if name in WILD_SCENES:
        return wild_inputs(name)
    from viewers.wild.protocol import natural_key
    from bench_direct.data.preprocess.colmap_io import read_images_binary, qvec2rotmat
    directory = ROOT / 'data/nvs/m360' / name
    paths = sorted((p for p in (directory/'images_4').iterdir()
                    if p.suffix.lower() in ('.jpg', '.jpeg', '.png')), key=natural_key)
    if len(paths) < 16:
        raise ValueError(f'{name}: need 16 images')
    ids = np.linspace(0, len(paths)-1, 16, dtype=int)
    cameras = {c.name: c for c in read_images_binary(directory/'sparse/0/images.bin').values()}
    frames = []
    from bench.io import digest
    for i in ids:
        p = paths[i]
        c = cameras[p.name]
        w2c = np.eye(4)
        w2c[:3, :3], w2c[:3, 3] = qvec2rotmat(c.qvec), c.tvec
        frames.append(dict(path=str(p.relative_to(ROOT)), sha256=digest(p), c2w=np.linalg.inv(w2c).tolist()))
    return dict(scene=name, frames=frames, input_frames=16, image_directory='images_4',
                sampling=dict(policy='uniform_linspace_natural_order', indices=ids.tolist(), available=len(paths)),
                seed=42, point_count=100000, camera_source='colmap_opencv_c2w')


class PlainSurflo:
    def __init__(self):
        sys.path.insert(0, str(ROOT/'external/Surflo'))
        from surflo.api import Surflo
        self.model = Surflo.from_checkpoint(str(ROOT/'ckpts/surflo/surflo_v0.pt'), device='cuda', use_ema=True)

    def predict(self, paths, valid_masks=None, num_points=200000):
        import torch
        from surflo.api import set_global_seeds
        from viewers.wild.benchmark_models import surflo_image_mask
        from demo.scripts.coloring import original_vggt_colors
        from demo.scripts.foreground import surflo_masks
        from bench.adapters.surflo import masked_source
        from contextlib import nullcontext
        set_global_seeds(42)
        with torch.no_grad():
            state = self.model.encode(paths, target_size=518, cull_radius=10.)
            mask = surflo_image_mask(paths, state.images)
            source = None
            if valid_masks is not None:
                mask &= surflo_masks(paths, valid_masks, state.images)
                depth = state.depth.reshape(mask.shape)
                valid = mask & torch.isfinite(depth) & (depth > 0) & torch.isfinite(state.world_points).all(-1)
                source = state.world_points[valid][None]
                if not source.shape[1]:
                    raise ValueError('No foreground source points for Surflo')
            with masked_source(state.model, source) if source is not None else nullcontext():
                result = state.reconstruct(mode='plain', num_query_points=num_points,
                    num_points_per_batch=min(200000, source.shape[1] if source is not None else num_points),
                    num_steps=100, seed=42)
        colors, coloring = original_vggt_colors(state, paths, result['points'], valid_mask=mask)
        return dict(points=result['points'], normals=result['normals'],
            colors=torch.as_tensor(colors, device=result['points'].device), coloring=coloring,
            images=state.images, mask=mask,
            extrinsics=state.extrinsics, intrinsics=state.intrinsics,
            metadata=dict(mode='plain', guidance=False, num_steps=100, use_ema=True,
                          num_query_points=num_points, foreground_mask_enabled=valid_masks is not None,
                          preprocessing='upstream_no_stretch_518', cull_radius=10.))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=DEST)
    parser.add_argument('--methods', nargs='+', choices=METHODS, default=list(METHODS))
    parser.add_argument('--scenes', nargs='+', choices=SCENES, default=list(SCENES))
    args = parser.parse_args()
    scenes = {name: scene_inputs(name) for name in args.scenes}
    from demo.scripts.import_bench import import_scene
    for name in list(scenes):
        if name == 'office':
            import_scene(scenes[name], args.output_root/name,
                         [method for method in args.methods if method != 'vsurf_final'])
            if 'vsurf_final' not in args.methods:
                scenes.pop(name)
        elif BENCH_SCENES.get(name) == 'dtu':
            import_scene(scenes.pop(name), args.output_root/name, args.methods)
    if not scenes:
        return
    import torch
    from bench.adapters.base import checkpoint_identity
    from bench.methods import DEFAULTS
    from bench.io import digest
    from viewers.wild.benchmark_models import OmegaVSurf
    import viewers.wild.benchmark as exporter
    for name, scene in scenes.items():
        folder = args.output_root/name
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'inputs.json').write_text(json.dumps(scene, indent=2)+'\n')
        save_thumbnail(name, scene, folder)
    # Image-only scenes need a shared Omega camera frame before exporting Surflo.
    needs_cameras = any(scene['camera_source'] == 'omega_native' for scene in scenes.values())
    ordered_methods = ['vggt_omega'] if needs_cameras else []
    ordered_methods += [method for method in args.methods if method not in ordered_methods]
    for method in ordered_methods:
        if method != 'vsurf_final' and all(name == 'office' for name in scenes):
            continue
        print(f'Loading {method}', flush=True)
        identity = checkpoint_identity(DEFAULTS[method])
        model = PlainSurflo() if method == 'surflo_plain' else OmegaVSurf('vsurf' if method == 'vsurf_final' else 'vggt-omega')
        if method == 'vsurf_final' and any(len(scene['frames']) > 64 for scene in scenes.values()):
            from viewers.largescale.generate import enable_chunked_mlps
            enable_chunked_mlps(model.pipeline.model)
        for name, scene in scenes.items():
            if name == 'office' and method != 'vsurf_final':
                continue
            if method not in args.methods and scene['camera_source'] != 'omega_native':
                continue
            print(f'{name}: {method}, {len(scene["frames"])} frames', flush=True)
            from demo.scripts.foreground import load_masks, ForegroundFilter
            masks = load_masks(scene)
            point_filter = ForegroundFilter(scene['frames'], masks) if masks is not None else None
            paths = [str(ROOT/f['path']) for f in scene['frames']]
            output = model.predict(paths, valid_masks=masks)
            if method == 'vggt_omega' and scene['camera_source'] == 'omega_native':
                from bench.geometry import homogeneous
                cameras = np.linalg.inv(homogeneous(output['extrinsics'].detach().float().cpu().numpy()))
                for frame, camera in zip(scene['frames'], cameras):
                    frame['c2w'] = camera.tolist()
                scene['reference_camera_checkpoint'] = identity
                (args.output_root/name/'inputs.json').write_text(json.dumps(scene, indent=2)+'\n')
            if method not in args.methods:
                del output
                gc.collect()
                torch.cuda.empty_cache()
                continue
            target = args.output_root/name/f'{method}.ply'
            export_scene = scene
            if scene['camera_source'] == 'omega_native' and method == 'surflo_plain':
                export_scene = dict(scene, camera_source='omega_predicted_c2w')
            record = exporter.export_prediction(output, export_scene, target,
                maximum=scene['point_count'], point_filter=point_filter)
            candidate_count = 200000
            while record['saved_points'] < scene['point_count'] and method == 'surflo_plain' and candidate_count < 1600000:
                candidate_count *= 2
                print(f'{name}: only {record["saved_points"]} foreground points; trying {candidate_count} Surflo candidates', flush=True)
                del output
                gc.collect(); torch.cuda.empty_cache()
                output = model.predict(paths, valid_masks=masks, num_points=candidate_count)
                record = exporter.export_prediction(output, export_scene, target,
                    maximum=scene['point_count'], point_filter=point_filter)
            if record['saved_points'] != scene['point_count']:
                raise ValueError(f'{name}/{method}: expected {scene["point_count"]} valid points, got {record["saved_points"]}')
            record.update(method=method, scene=name, model_metadata=output['metadata'],
                          checkpoint_identity=identity, inputs_sha256=digest(args.output_root/name/'inputs.json'),
                          ply_sha256=digest(target))
            (args.output_root/name/f'{method}.json').write_text(json.dumps(record, indent=2)+'\n')
            print(f'Exported {target}: {record["saved_points"]} points', flush=True)
            del output
            gc.collect()
            torch.cuda.empty_cache()
        del model
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == '__main__':
    main()
