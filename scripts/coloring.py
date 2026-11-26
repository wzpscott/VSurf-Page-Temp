"""Transfer the original VGGT cloud's pixel RGB to Surflo's reconstructed points."""
import numpy as np


def original_vggt_colors(state, paths, points, valid_mask=None):
    import torch
    from scipy.spatial import cKDTree
    from viewers.wild.benchmark_models import surflo_image_mask

    mask = surflo_image_mask(paths, state.images)
    if valid_mask is not None:
        mask &= valid_mask
    depth = state.depth.reshape(mask.shape)
    valid = mask & torch.isfinite(depth) & (depth > 0) & torch.isfinite(state.world_points).all(-1)
    source = state.world_points[valid].detach().float().cpu().numpy()
    rgb = state.images.permute(0, 2, 3, 1)[valid].detach().float().cpu().numpy()
    queries = points.detach().float().cpu().numpy() if isinstance(points, torch.Tensor) else np.asarray(points)
    if not len(source) or not np.isfinite(queries).all():
        raise ValueError('Expected valid original VGGT points and finite Surflo points')
    _, indices = cKDTree(source).query(queries, workers=8)
    return rgb[indices], dict(policy='original_vggt_nearest_neighbor_rgb',
                             source='surflo_original_vggt', source_points=len(source), neighbors=1)
