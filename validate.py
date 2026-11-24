"""Validate actual demo assets and their generation provenance (CPU only)."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from demo.generate import SCENES, BENCH_SCENES

ROOT = Path(__file__).resolve().parent
DTYPE = np.dtype([(k, '<f4') for k in ('x','y','z','nx','ny','nz')]
                 + [(k, 'u1') for k in ('red','green','blue')])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-root', type=Path, default=ROOT/'assets')
    parser.add_argument('--scenes', nargs='+', choices=SCENES, default=list(SCENES))
    args = parser.parse_args()
    for scene in args.scenes:
        folder = args.asset_root/scene
        inputs = json.loads((folder/'inputs.json').read_text())
        point_count = 100000
        assert inputs['point_count'] == point_count
        count = ((49 if BENCH_SCENES[scene] == 'dtu' else 100) if scene in BENCH_SCENES else
                 256 if scene == 'rubble' else 128 if scene == 'stadium' else 11 if scene == 'valley' else 16)
        assert inputs['input_frames'] == len(inputs['frames']) == count
        assert len({f['path'] for f in inputs['frames']}) == count
        if scene in ('counter', 'garden'):
            assert all('/images_4/' in f['path'] for f in inputs['frames'])
        cameras = np.asarray([f['c2w'] for f in inputs['frames']])
        assert cameras.shape == (count, 4, 4) and np.isfinite(cameras).all()
        sample = inputs['sampling']
        if scene == 'stadium':
            assert sample['policy'] == 'uniform_linspace_natural_order'
            assert sample['available'] >= count
        assert sample['indices'] == np.linspace(0, sample['available']-1, count, dtype=int).tolist()
        assert (folder/'thumbnail.jpg').is_file()
        if (folder/'thumbnail.json').exists():
            thumbnail = json.loads((folder/'thumbnail.json').read_text())
            assert thumbnail['thumbnail_sha256'] == digest(folder/'thumbnail.jpg')
        foreground = None
        imported = inputs.get('asset_source') == 'bench_viewer_ply'
        if BENCH_SCENES.get(scene) == 'dtu' and not imported:
            from demo.foreground import ForegroundFilter, load_masks
            assert inputs['foreground_mask_policy'] == 'dtu_foreground_only'
            for frame in inputs['frames']:
                assert digest(Path(frame['mask_path'])) == frame['mask_sha256']
            foreground = ForegroundFilter(inputs['frames'], load_masks(inputs))
        for method in ('vsurf_final', 'vggt_omega', 'surflo_plain'):
            path = folder/f'{method}.ply'
            record = json.loads((folder/f'{method}.json').read_text())
            imported = record.get('asset_source') == 'bench_viewer_ply'
            assert record['inputs_sha256'] == digest(folder/'inputs.json')
            assert record['ply_sha256'] == digest(path)
            assert record['saved_points'] == point_count
            with path.open('rb') as stream:
                header = []
                while True:
                    line = stream.readline()
                    assert line, 'Missing PLY header terminator'
                    header.append(line)
                    if line == b'end_header\n': break
                assert f'element vertex {point_count}\n'.encode() in header
                vertices = np.frombuffer(stream.read(), dtype=DTYPE)
            assert len(vertices) == point_count
            data = np.column_stack([vertices[k] for k in DTYPE.names[:6]])
            assert np.isfinite(data).all()
            assert np.allclose(np.linalg.norm(data[:,3:],axis=1),1,atol=1e-5)
            if foreground is not None:
                assert record['foreground_filter']['policy'] == 'dtu_foreground_only'
                assert record['model_metadata']['foreground_mask_enabled'] is True
                assert foreground(data[:, :3]).all(), 'DTU export contains background points'
            if method == 'surflo_plain':
                assert record['model_metadata']['mode'] == 'plain'
                if imported:
                    assert record['coloring']['source'] == 'original_vggt_point_cloud'
                else:
                    assert record['model_metadata']['guidance'] is False
                    assert record['coloring']['policy'] == 'original_vggt_nearest_neighbor_rgb'
                    assert record['coloring']['source'] == 'surflo_original_vggt'
            if imported:
                assert record['asset_source'] == 'bench_viewer_ply'
                assert record['input_mask']['dataset_mask_enabled'] is True
                assert record['bench_source']['ply_sha256'] == digest(path)
                assert digest(ROOT.parent/record['bench_source']['path']) == digest(path)
            elif method == 'vsurf_final':
                assert record['model_metadata']['architecture'] == 'vsurf_final'
                assert record['model_metadata']['tto_steps'] == 0
                assert record['model_metadata']['normalization']['mode'] == 'median_point_radius'
            print(f'{scene}/{method}: {point_count:,} valid colored, oriented points; provenance verified')
    assert not any(p.is_symlink() for p in ROOT.rglob('*')), 'Demo must not depend on external symlinks'


if __name__ == '__main__':
    main()
