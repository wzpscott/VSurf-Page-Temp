import * as THREE from 'three';
export function createRenderer({ transparent = false, background = 0xf0f2ee } = {}) {
    const renderer = new THREE.WebGLRenderer({antialias: true, alpha: transparent});
    renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio || 1, 2));
    renderer.setClearColor(background, transparent ? 0 : 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.tabIndex = 0;
    return renderer;
}
export function synchronize(views, render) {
    let syncing = false;
    for (const source of views) source.controls.addEventListener('change', () => {
        if (syncing) return;
        syncing = true;
        for (const target of views) if (target !== source) {
            target.camera.position.copy(source.camera.position);
            target.camera.quaternion.copy(source.camera.quaternion);
            target.camera.up.copy(source.camera.up);
            target.controls.target.copy(source.controls.target);
            target.controls.update();
        }
        syncing = false; render();
    });
}
export function pointSize(material, size, renderer) {
    if (material.uniforms?.pointSize) material.uniforms.pointSize.value = size * renderer.getPixelRatio();
    else material.size = size;
}
