"""Copy published bench clouds exactly, retaining their reconstruction provenance."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def import_scene(scene, folder, methods):
    from bench.io import digest
    from demo.generate import save_thumbnail
    catalog_path = ROOT/'viewers/bench/assets/catalog.json'
    catalog = json.loads(catalog_path.read_text())
    dataset, name = scene['source_scene'].split('/')
    group = next(d for d in catalog['datasets'] if d['id'] == dataset)
    source = next(s for s in group['scenes'] if s['id'] == name)
    reports = json.loads((ROOT/f'viewers/bench/assets/metrics/{dataset}.json').read_text())['scenes'][name]
    pending = []
    for method in methods:
        asset = source['assets'][method]
        path = ROOT/'viewers/bench'/asset['url']
        if not asset['available'] or digest(path) != asset['ply_sha256']:
            raise ValueError(f'{name}/{method}: missing or changed bench PLY')
        if asset['points'] != scene['point_count'] or asset['input_frames'] != scene['input_frames']:
            raise ValueError(f'{name}/{method}: incompatible bench counts')
        record = dict(reports[method])
        pending.append((method, path, asset, record))
    scene.update(asset_source='mixed_demo_and_bench' if name == 'office' else 'bench_viewer_ply', foreground_mask_policy='bench_dataset_foreground' if dataset == 'dtu' else 'bench_dataset_mask',
                 display_rotation=source['display_rotation'])
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'inputs.json').write_text(json.dumps(scene, indent=2)+'\n')
    save_thumbnail(name, scene, folder)
    for method, path, asset, record in pending:
        target = folder/f'{method}.ply'
        staged = target.with_name(target.name+'.tmp')
        shutil.copyfile(path, staged)
        staged.replace(target)
        record.update(method=method, scene=name, saved_points=asset['points'],
                      ply_sha256=asset['ply_sha256'], inputs_sha256=digest(folder/'inputs.json'),
                      asset_source='bench_viewer_ply',
                      bench_source=dict(path=str(path.relative_to(ROOT)), ply_sha256=asset['ply_sha256'],
                                        catalog_sha256=digest(catalog_path), record_sha256=asset['record_sha256']))
        (folder/f'{method}.json').write_text(json.dumps(record, indent=2)+'\n')
        print(f'{name}/{method}: copied exact bench PLY ({asset["points"]:,} points)', flush=True)
