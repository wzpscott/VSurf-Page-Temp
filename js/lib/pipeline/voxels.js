import * as THREE from 'three';
import { pcaColor } from './palette.js';

export function voxelMatrices(geometry, size, fill, write) {
    const positions = geometry.getAttribute('position');
    const matrix = new THREE.Matrix4();
    for (let i = 0; i < positions.count; i++) {
        matrix.makeScale(...size.map(value => value * fill));
        matrix.setPosition(positions.getX(i), positions.getY(i), positions.getZ(i));
        write(i, matrix);
    }
}

export function createVoxels(geometry, size, fill = 0.9, { pca = true, pooledColors = null, edgeWidth = 2, solidEdges = false } = {}) {
    const material = new THREE.ShaderMaterial({
        uniforms: { edgeLimit: { value: pca ? 1.0 : 0.08 },
            edgeWidth: { value: edgeWidth }, solidEdges: { value: solidEdges ? 1 : 0 } },
        vertexShader: `
            varying vec2 faceUv;
            varying vec3 voxelColor;
            void main() {
                faceUv = uv;
                voxelColor = instanceColor;
                gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
            }`,
        fragmentShader: `
            uniform float edgeLimit;
            uniform float edgeWidth;
            uniform float solidEdges;
            varying vec2 faceUv;
            varying vec3 voxelColor;
            void main() {
                vec2 edge = min(faceUv, 1.0 - faceUv);
                vec2 aa = max(fwidth(faceUv), vec2(0.0001));
                vec2 width = min(aa * edgeWidth, vec2(edgeLimit));
                vec2 interior = edgeWidth <= 0.0 ? vec2(1.0) : smoothstep(max(width - aa, vec2(0.0)) * solidEdges, width, edge);
                gl_FragColor = vec4(mix(vec3(0.035), voxelColor, min(interior.x, interior.y)), 1.0);
                #include <colorspace_fragment>
            }`,
        toneMapped: false,
    });
    const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), material,
        geometry.getAttribute('position').count);
    const colors = geometry.getAttribute('color');
    const color = new THREE.Color();
    if (pca) {
        // Undo PLYLoader's sRGB decoding to recover the original PCA scores.
        const scores = Array.from({ length: colors.count }, (_, i) => {
            color.setRGB(colors.getX(i), colors.getY(i), colors.getZ(i)).convertLinearToSRGB();
            return [color.r, color.g, color.b];
        });
        let palette = 'perceptual', reversed = false, colorMode = 'pca';
        const updateColors = () => {
            scores.forEach((score, i) => {
                if (colorMode === 'rgb') color.setRGB(pooledColors.getX(i), pooledColors.getY(i), pooledColors.getZ(i));
                else color.setRGB(...pcaColor(score, palette, reversed));
                mesh.setColorAt(i, color);
            });
            mesh.instanceColor.needsUpdate = true;
        };
        mesh.userData.setColorMode = mode => {
            if (!['pca', 'rgb'].includes(mode) || (mode === 'rgb' && pooledColors?.count !== colors.count))
                throw new Error('Pooled point colors are unavailable');
            colorMode = mode; updateColors();
        };
        updateColors();
        mesh.userData.setReversePca = value => { reversed = value; updateColors(); };
        mesh.userData.setPalette = value => { palette = value; updateColors(); };
    } else {
        for (let i = 0; i < colors.count; i++) {
            mesh.setColorAt(i, color.setRGB(colors.getX(i), colors.getY(i), colors.getZ(i)));
        }
        mesh.instanceColor.needsUpdate = true;
    }
    mesh.userData.setEdgeWidth = value => {
        if (!Number.isFinite(value) || value < 0) throw new Error('Invalid voxel outline width');
        material.uniforms.edgeWidth.value = value;
    };
    mesh.userData.setFill = value => {
        voxelMatrices(geometry, size, value, (i, matrix) => mesh.setMatrixAt(i, matrix));
        mesh.instanceMatrix.needsUpdate = true;
        mesh.computeBoundingSphere();
    };
    mesh.userData.setFill(fill);
    mesh.userData.dispose = () => { mesh.geometry.dispose(); material.dispose(); mesh.dispose(); };
    return mesh;
}
