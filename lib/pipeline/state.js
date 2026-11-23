export const panels = [
    {id: 'input', title: '(a) Frontend points', space: 'world'},
    {id: 'voxelized', title: '(b) Contractive voxelization', space: 'contracted'},
    {id: 'pruner', title: '(c) Structured Scene States', space: 'contracted', feature: true, voxels: true},
    {id: 'output', title: '(d) Surface points', space: 'world'},
    {id: 'output', title: '(e) Surface normals', space: 'world', normals: true},
];

export function validateGeometry(geometry, requireNormals = false) {
    try {
        const position = geometry.getAttribute('position');
        if (!position?.count) throw new Error('Cloud has no points');
        for (const name of ['position', 'color', ...(requireNormals ? ['normal'] : [])]) {
            const attribute = geometry.getAttribute(name);
            if (!attribute || attribute.itemSize !== 3 || attribute.count !== position.count ||
                !attribute.array.every(Number.isFinite)) throw new Error(`Invalid ${name} attribute`);
        }
        if (requireNormals) {
            const normal = geometry.getAttribute('normal');
            for (let i = 0; i < normal.count; i++) {
                const length = Math.hypot(normal.getX(i), normal.getY(i), normal.getZ(i));
                if (length < 1e-8) throw new Error('Invalid zero-length normal');
                normal.setXYZ(i, normal.getX(i) / length, normal.getY(i) / length, normal.getZ(i) / length);
            }
        }
        geometry.setIndex(null);
        geometry.rotateX(Math.PI);
        geometry.computeBoundingBox();
        geometry.computeBoundingSphere();
        return geometry;
    } catch (error) {
        geometry.dispose();
        throw error;
    }
}


export function panelVoxelSize(panel, metadata) {
    if (panel.feature) return metadata.feature_voxel_size;
    const resolution = metadata.display_input_resolution;
    const size = metadata.bounds?.map(([lo, hi]) => (hi - lo) / resolution);
    if (!Number.isInteger(resolution) || resolution < 1 || size?.length !== 3 ||
        !size.every(v => Number.isFinite(v) && v > 0)) {
        throw new Error('Invalid contracted input voxel grid');
    }
    return size;
}
