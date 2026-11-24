"""DTU foreground silhouettes, independent of depth/GT geometry filters."""
import numpy as np
from PIL import Image


def load_masks(scene):
    if scene.get('foreground_mask_policy') != 'dtu_foreground_only':
        return None
    masks = []
    for frame in scene['frames']:
        with Image.open(frame['mask_path']) as image:
            masks.append(np.asarray(image) > 0)
    return masks


def surflo_masks(paths, masks, images):
    """Mirror upstream no_stretch/ROTATE_90/crop/padding, using nearest labels."""
    import torch
    height, width = images.shape[-2:]
    output = []
    for path, valid in zip(paths, masks):
        with Image.open(path) as image:
            original_size = image.size
        mask = Image.fromarray(np.asarray(valid, dtype=np.uint8) * 255)
        if mask.size != original_size:
            raise ValueError('Foreground mask must match the source image')
        if mask.height > mask.width:
            mask = mask.transpose(Image.Transpose.ROTATE_90)
        w, h = mask.size
        scale = 518 / max(w, h)
        rw, rh = round(w * scale), round(h * scale)
        mask = mask.resize((rw, rh), Image.Resampling.NEAREST)
        cw = int(w * scale / 14) * 14 if rw % 14 else rw
        ch = int(h * scale / 14) * 14 if rh % 14 else rh
        mask = mask.crop((rw//2-cw//2, rh//2-ch//2, rw//2+cw//2, rh//2+ch//2))
        if cw > width or ch > height or min(cw, ch) < 14:
            raise ValueError('Unexpected Surflo image dimensions')
        canvas = np.zeros((height, width), dtype=bool)
        x, y = (width-cw)//2, (height-ch)//2
        canvas[y:y+ch, x:x+cw] = np.asarray(mask) > 0
        output.append(canvas)
    return torch.from_numpy(np.stack(output)).to(images.device)


class ForegroundFilter:
    """Keep points supported by silhouettes and never observed on background."""
    def __init__(self, frames, masks):
        if len(frames) != len(masks) or not frames:
            raise ValueError('Need matching reference cameras and foreground masks')
        self.views = [(np.linalg.inv(np.asarray(f['c2w'])), np.asarray(f['intrinsics']), mask)
                      for f, mask in zip(frames, masks)]

    def __call__(self, points):
        # Test precisely the coordinates that the display PLY will contain.
        points = np.asarray(points, dtype=np.float32).astype(np.float64)
        keep = np.zeros(len(points), dtype=bool)
        for start in range(0, len(points), 131072):
            p = points[start:start+131072]
            supported = np.zeros(len(p), dtype=bool)
            rejected = ~np.isfinite(p).all(1)
            for w2c, k, mask in self.views:
                local = p @ w2c[:3, :3].T + w2c[:3, 3]
                projected = local @ k.T
                uv = projected[:, :2] / np.where(projected[:, 2:] > 0, projected[:, 2:], 1)
                h, w = mask.shape
                inside = ((local[:, 2] > 0) & np.isfinite(uv).all(1) &
                          (uv[:, 0] >= 0) & (uv[:, 0] < w) & (uv[:, 1] >= 0) & (uv[:, 1] < h))
                ids = np.flatnonzero(inside)
                xy = np.floor(uv[ids]).astype(np.int64)
                foreground = mask[xy[:, 1], xy[:, 0]]
                supported[ids] |= foreground
                rejected[ids] |= ~foreground
            keep[start:start+len(p)] = supported & ~rejected
        return keep
