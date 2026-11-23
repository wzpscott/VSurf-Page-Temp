// Map camera coordinates through each panel's framing sphere. This preserves
// orientation and relative zoom/pan across contracted and world-space stages.
export function mapFramePoint(point, source, target) {
    return point.clone().sub(source.center).multiplyScalar(target.radius / source.radius).add(target.center);
}

export function synchronizeFrames(views, render) {
    let syncing = false;
    const suspend = action => {
        const previous = syncing;
        syncing = true;
        try { action(); } finally { syncing = previous; }
    };
    for (const source of views) source.controls.addEventListener('change', () => {
        if (syncing || !source.frame) return;
        suspend(() => {
            for (const target of views) if (target !== source && target.frame) {
                target.camera.position.copy(mapFramePoint(source.camera.position, source.frame, target.frame));
                target.controls.target.copy(mapFramePoint(source.controls.target, source.frame, target.frame));
                target.camera.quaternion.copy(source.camera.quaternion);
                target.camera.up.copy(source.camera.up);
                target.controls.update();
            }
        });
        render();
    });
    return { suspend };
}
