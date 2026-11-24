"""Reconstruct full VSurf predictions for the standalone mesh demo."""
import argparse
import gc
import json
from pathlib import Path
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCENES = ('green_room', 'pyramid', 'stadium')
POISSON_DEPTH = 10
DENSITY_QUANTILE = 0.02
MAX_TRIANGLES = 500000


def inference_scene(scene):
    """Use the saved DTU silhouettes when regenerating imported demo scenes."""
    if scene.get('source_scene', '').startswith('dtu/'):
        return dict(scene, foreground_mask_policy='dtu_foreground_only')
    return scene


def trim_density(mesh, densities, quantile=DENSITY_QUANTILE):
    densities = np.asarray(densities)
    if densities.shape != (len(mesh.vertices),) or not np.isfinite(densities).all():
        raise ValueError('Invalid Poisson vertex densities')
    if quantile == 0:
        return None
    threshold = float(np.quantile(densities, quantile))
    mesh.remove_vertices_by_mask(densities < threshold)
    mesh.remove_unreferenced_vertices()
    return threshold


def clean_mesh(mesh):
    mesh.remove_degenerate_triangles().remove_duplicated_triangles().remove_unreferenced_vertices()
    # Open3D's degenerate-triangle removal only handles repeated vertex indices.
    # Poisson/decimation can also produce collinear triangles and opposing faces
    # whose incident normals cancel; these cannot be shaded with a unit normal.
    vertices, faces = np.asarray(mesh.vertices), np.asarray(mesh.triangles)
    if len(faces):
        area = np.linalg.norm(np.cross(vertices[faces[:, 1]]-vertices[faces[:, 0]],
                                       vertices[faces[:, 2]]-vertices[faces[:, 0]]), axis=1)
        mesh.remove_triangles_by_mask(area == 0)
        mesh.remove_unreferenced_vertices()
    while len(mesh.vertices):
        mesh.compute_vertex_normals()
        invalid = np.linalg.norm(np.asarray(mesh.vertex_normals), axis=1) < 0.99
        if not invalid.any():
            break
        mesh.remove_vertices_by_mask(invalid)
        mesh.remove_unreferenced_vertices()
    return mesh


def simplify(mesh, maximum=MAX_TRIANGLES):
    clean_mesh(mesh)
    while len(mesh.triangles) > maximum:
        before = len(mesh.triangles)
        mesh = mesh.simplify_quadric_decimation(maximum)
        clean_mesh(mesh)
        if len(mesh.triangles) >= before:
            raise ValueError('Decimation failed to reduce triangle count')
    mesh.compute_vertex_normals()
    validate_mesh(mesh, maximum)
    return mesh


def validate_mesh(mesh, maximum=MAX_TRIANGLES):
    vertices, faces = np.asarray(mesh.vertices), np.asarray(mesh.triangles)
    colors, normals = np.asarray(mesh.vertex_colors), np.asarray(mesh.vertex_normals)
    if not len(vertices) or not 0 < len(faces) <= maximum:
        raise ValueError('Empty mesh or triangle budget exceeded')
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError('Invalid triangle indices')
    if colors.shape != vertices.shape or normals.shape != vertices.shape:
        raise ValueError('Missing vertex colors or normals')
    if not all(np.isfinite(a).all() for a in (vertices, normals, colors)):
        raise ValueError('Nonfinite mesh attributes')
    if np.any(np.linalg.norm(normals, axis=1) < 0.99):
        raise ValueError('Invalid vertex normals')


def write_mesh_float32(path, mesh):
    """Write indexed binary PLY: float32 XYZ/normals, uint8 RGB, uint32 faces."""
    import open3d as o3d
    # Validate geometry at the precision actually served to the browser.
    mesh.vertices = o3d.utility.Vector3dVector(np.asarray(mesh.vertices).astype(np.float32))
    clean_mesh(mesh)
    validate_mesh(mesh)
    vertices = np.empty(len(mesh.vertices), dtype=[(k, '<f4') for k in ('x','y','z','nx','ny','nz')]
                        + [(k, 'u1') for k in ('red','green','blue')])
    for fields, values in [(('x','y','z'), np.asarray(mesh.vertices)),
                           (('nx','ny','nz'), np.asarray(mesh.vertex_normals)),
                           (('red','green','blue'), np.rint(np.clip(np.asarray(mesh.vertex_colors), 0, 1)*255))]:
        for i, key in enumerate(fields):
            vertices[key] = values[:, i]
    faces = np.empty(len(mesh.triangles), dtype=[('count', 'u1'), ('indices', '<u4', (3,))])
    faces['count'] = 3
    faces['indices'] = np.asarray(mesh.triangles)
    header = ('ply\nformat binary_little_endian 1.0\n'
              f'element vertex {len(vertices)}\n'
              + ''.join(f'property float {k}\n' for k in ('x','y','z','nx','ny','nz'))
              + ''.join(f'property uchar {k}\n' for k in ('red','green','blue'))
              + f'element face {len(faces)}\nproperty list uchar uint vertex_indices\nend_header\n')
    with Path(path).open('wb') as stream:
        stream.write(header.encode('ascii'))
        vertices.tofile(stream)
        faces.tofile(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes', nargs='+', choices=SCENES, default=list(SCENES))
    parser.add_argument('--output-root', type=Path, default=ROOT/'outputs/demo_mesh/assets')
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--reuse-points', action='store_true', help='Reuse verified full predictions in the output directory')
    args = parser.parse_args()
    import open3d as o3d
    import torch
    from bench.io import digest
    from bench.adapters.base import checkpoint_identity
    from bench.methods import DEFAULTS
    from viewers.wild.benchmark_models import OmegaVSurf
    from viewers.wild.benchmark import export_prediction
    from viewers.largescale.generate import enable_chunked_mlps
    from demo.foreground import load_masks, ForegroundFilter

    model = None
    identity = checkpoint_identity(DEFAULTS['vsurf_final'])
    for name in args.scenes:
        start = time.perf_counter()
        folder = args.output_root/name
        folder.mkdir(parents=True, exist_ok=True)
        source = ROOT/'demo/assets'/name/'inputs.json'
        scene = inference_scene(json.loads(source.read_text()))
        points_path, record_path = folder/'full_points.ply', folder/'full_points.json'
        if args.reuse_points and points_path.exists() and record_path.exists():
            record = json.loads(record_path.read_text())
            if (record['inputs_sha256'] != digest(source) or record['ply_sha256'] != digest(points_path)
                    or record['checkpoint_identity'] != identity):
                raise ValueError('Cached full prediction provenance mismatch')
        else:
            for frame in scene['frames']:
                if digest(ROOT/frame['path']) != frame['sha256']:
                    raise ValueError(f'Input changed: {frame["path"]}')
                if scene.get('foreground_mask_policy') == 'dtu_foreground_only':
                    if digest(ROOT/frame['mask_path']) != frame['mask_sha256']:
                        raise ValueError(f'Mask changed: {frame["mask_path"]}')
            if model is None:
                model = OmegaVSurf('vsurf')
                enable_chunked_mlps(model.pipeline.model)
            print(f'{name}: predicting all VSurf points', flush=True)
            masks = load_masks(scene)
            point_filter = ForegroundFilter(scene['frames'], masks) if masks is not None else None
            output = model.predict([str(ROOT/f['path']) for f in scene['frames']], valid_masks=masks)
            record = export_prediction(output, scene, points_path, maximum=len(output['points']),
                                       point_filter=point_filter)
            record.update(inputs_sha256=digest(source), ply_sha256=digest(points_path),
                          checkpoint_identity=identity, model_metadata=output['metadata'], timing=output['timing'])
            record_path.write_text(json.dumps(record, indent=2)+'\n')
            del output
            gc.collect()
            torch.cuda.empty_cache()
        cloud = o3d.io.read_point_cloud(str(points_path))
        retained = record.get('foreground_filter', {}).get('retained_points', record['raw_points'])
        if len(cloud.points) != retained or len(cloud.points) != record['saved_points']:
            raise ValueError('Full prediction was unexpectedly sampled')
        depth = POISSON_DEPTH
        print(f'{name}: Poisson depth={depth}, {len(cloud.points):,} points', flush=True)
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            cloud, depth=depth, n_threads=args.threads)
        raw_vertices = len(mesh.vertices)
        density_quantile = DENSITY_QUANTILE
        threshold = trim_density(mesh, densities, density_quantile)
        trimmed_vertices = len(mesh.vertices)
        mesh = simplify(mesh)
        target = folder/'mesh.ply'
        write_mesh_float32(target, mesh)
        validate_mesh(o3d.io.read_triangle_mesh(str(target)))
        metadata = dict(scene=name, method='screened_poisson', depth=depth, density_quantile=density_quantile,
                        density_threshold=threshold, max_triangles=MAX_TRIANGLES, raw_vertices=raw_vertices,
                        position_dtype='float32', normal_dtype='float32', color_dtype='uint8', index_dtype='uint32',
                        trimmed_vertices=trimmed_vertices, vertices=len(mesh.vertices), triangles=len(mesh.triangles),
                        source_points=len(cloud.points), inputs_sha256=digest(source),
                        source_prediction=record, ply_sha256=digest(target), open3d_version=o3d.__version__,
                        elapsed_seconds=time.perf_counter()-start)
        (folder/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
        print(f'{name}: validated {len(mesh.vertices):,} vertices, {len(mesh.triangles):,} triangles', flush=True)
        del cloud, mesh, densities
        gc.collect()


if __name__ == '__main__':
    main()
