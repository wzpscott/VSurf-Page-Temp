import * as THREE from 'three';

// Model-frame clouds default to the OpenCV display rotation. Native GT-frame
// clouds can supply rotationX=0; positions and normals always transform together.
export function preparePointGeometry(geometry, {rotationX = Math.PI} = {}) {
    const position = geometry.getAttribute('position');
    const normal = geometry.getAttribute('normal');
    const color = geometry.getAttribute('color');
    try {
        if (!position?.count || position.itemSize !== 3 ||
            (normal?.count !== position.count || normal.itemSize !== 3) ||
            color?.count !== position.count || color.itemSize !== 3) {
            throw new Error('PLY requires XYZ, RGB colors, and normals for every point.');
        }
        for (let i = 0; i < position.count; i++) {
            for (const attribute of [position, normal, color]) {
                if (![attribute.getX(i), attribute.getY(i), attribute.getZ(i)].every(Number.isFinite)) {
                    throw new Error('PLY contains nonfinite point attributes.');
                }
            }
            const length = Math.hypot(normal.getX(i), normal.getY(i), normal.getZ(i));
            if (length <= 1e-8) throw new Error('PLY contains a zero-length normal.');
            normal.setXYZ(i, normal.getX(i) / length, normal.getY(i) / length, normal.getZ(i) / length);
        }
        // Render each vertex once, even if a supplied PLY also contains faces.
        geometry.setIndex(null);
        if (rotationX !== 0) geometry.rotateX(rotationX);
        geometry.computeBoundingBox();
        geometry.computeBoundingSphere();
        return geometry;
    } catch (error) {
        geometry.dispose();
        throw error;
    }
}

export function createPointMaterials() {
    return {
        rgb: new THREE.PointsMaterial({ size: 2, sizeAttenuation: false, vertexColors: true, toneMapped: false }),
        normals: new THREE.ShaderMaterial({
            uniforms: { pointSize: { value: 2 } },
            vertexShader: `
                uniform float pointSize;
                varying vec3 viewNormal;
                void main() {
                    viewNormal = normalize(normalMatrix * normal);
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                    gl_PointSize = pointSize;
                }
            `,
            fragmentShader: `
                varying vec3 viewNormal;
                void main() {
                    gl_FragColor = vec4(normalize(viewNormal) * 0.5 + 0.5, 1.0);
                    #include <colorspace_fragment>
                }
            `,
            toneMapped: false,
        }),
    };
}

export function materialForAppearance(appearance, materials) {
    return appearance === 'rgb' ? materials.rgb : materials.normals;
}

export function setPointSize(materials, size) {
    materials.rgb.size = size;
    materials.normals.uniforms.pointSize.value = size;
}
