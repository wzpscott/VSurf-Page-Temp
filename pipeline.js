import {readAsset} from './lib/assets.js';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {PLYLoader} from 'three/addons/loaders/PLYLoader.js';
import {createRenderer, pointSize} from './lib/runtime.js';
import {createPointMaterials} from './lib/points.js';
import {panels, validateGeometry, panelVoxelSize} from './lib/pipeline/state.js';
import {createVoxels} from './lib/pipeline/voxels.js';
import {synchronizeFrames} from './lib/pipeline/camera.js';

const root = document.querySelector('#method-pipeline');
const status = root.querySelector('[role="status"]');
const slider = root.querySelector('input');
const resetButton = root.querySelector('button');
const views = [];
let synchronization, started = false;
const render = () => views.forEach(v => v.renderer.render(v.scene, v.camera));

function reset() {
    if (!synchronization) return;
    synchronization.suspend(() => {
        for (const view of views) {
            if (!view.frame) continue;
            const vertical = THREE.MathUtils.degToRad(view.camera.fov / 2);
            const horizontal = Math.atan(Math.tan(vertical) * Math.min(...views.map(v => v.camera.aspect)));
            const distance = view.frame.radius / Math.sin(Math.min(vertical, horizontal)) * 0.54;
            view.controls.target.copy(view.frame.center);
            view.camera.position.copy(view.frame.center).add(new THREE.Vector3(0, 0, distance));
            view.camera.up.set(0, 1, 0);
            view.camera.near = Math.max(.0001, view.frame.radius / 1000);
            view.camera.far = Math.max(100, distance + view.extent * 4);
            view.camera.updateProjectionMatrix();
            view.controls.update();
        }
    });
    render();
}

async function start() {
    if (started) return;
    started = true;
    const ownedGeometries = [];
    try {
        for (const panel of panels) {
            const element = document.createElement('article');
            element.className = 'pipeline-panel';
            element.innerHTML = `<div class="viewport"><span class="viewer-message">Loading…</span></div><h3>${panel.title}</h3>`;
            root.querySelector('.pipeline-panels').append(element);
            const viewport = element.querySelector('.viewport');
            const renderer = createRenderer({transparent: true});
            viewport.prepend(renderer.domElement);
            const camera = new THREE.PerspectiveCamera(45, 4 / 3, .001, 100);
            const controls = new OrbitControls(camera, renderer.domElement);
            const materials = createPointMaterials();
            const material = panel.normals ? materials.normals : materials.rgb;
            (panel.normals ? materials.rgb : materials.normals).dispose();
            pointSize(material, Number(slider.value), renderer);
            const view = {panel, element, viewport, renderer, camera, controls, material, scene: new THREE.Scene()};
            views.push(view);
            view.resize = new ResizeObserver(() => {
                const {width, height} = viewport.getBoundingClientRect();
                if (!width || !height) return;
                renderer.setSize(width, height, false);
                camera.aspect = width / height;
                camera.updateProjectionMatrix();
                render();
            });
            view.resize.observe(viewport);
        }
        synchronization = synchronizeFrames(views, render);
        const base = new URL('./assets/pipeline/counter/', document.baseURI);
        const metadata = await readAsset(new URL('metadata.json', base), {json:true});
        if (metadata.version !== 3 || metadata.coordinate_space !== 'mixed' ||
            metadata.display_input_resolution !== 1024 || metadata.contraction?.radius_multiplier !== 2 ||
            metadata.coordinate_mode !== 'spherical_contraction' || metadata.use_contraction !== true ||
            !panels.every(p => metadata.stage_spaces?.[p.id] === p.space) ||
            !['world', 'contracted'].every(space => {
                const box = metadata.framing_bounds?.[space];
                return box?.length === 2 && box.every(row => row.length === 3 && row.every(Number.isFinite)) &&
                    box[0].every((value, axis) => value < box[1][axis]);
            }) || metadata.feature_voxel_size?.length !== 3 ||
            !metadata.feature_voxel_size.every(v => Number.isFinite(v) && v > 0)) {
            throw new Error('Pipeline metadata is invalid.');
        }
        const loader = new PLYLoader();
        const results = await Promise.allSettled(['input', 'voxelized', 'pruner', 'output'].map(async id => {
            const bytes = await readAsset(new URL(`${id}.ply`, base));
            const geometry = validateGeometry(loader.parse(bytes), id === 'output');
            ownedGeometries.push(geometry);
            if (geometry.getAttribute('position').count !== metadata.counts[id]) throw new Error(`${id}: unexpected point count.`);
            return [id, geometry];
        }));
        const failure = results.find(result => result.status === 'rejected');
        if (failure) throw failure.reason;
        const geometries = Object.fromEntries(results.map(result => result.value));
        const frames = Object.fromEntries(Object.entries(metadata.framing_bounds).map(([space, box]) => {
            const bounds = new THREE.Box3(new THREE.Vector3(...box[0]), new THREE.Vector3(...box[1]));
            bounds.applyMatrix4(new THREE.Matrix4().makeRotationX(Math.PI));
            return [space, bounds.getBoundingSphere(new THREE.Sphere())];
        }));
        for (const view of views) {
            const geometry = geometries[view.panel.id];
            view.frame = frames[view.panel.space];
            view.extent = geometry.boundingSphere.center.distanceTo(view.frame.center) + geometry.boundingSphere.radius;
            view.cloud = view.panel.voxels
                ? createVoxels(geometry, panelVoxelSize(view.panel, metadata), .9, {pca: true})
                : new THREE.Points(geometry, view.material);
            view.scene.add(view.cloud);
            view.element.querySelector('.viewer-message').hidden = true;
        }
        slider.disabled = resetButton.disabled = false;
        status.textContent = '';
        reset();
    } catch (error) {
        for (const view of views) {
            if (view.cloud) { view.scene.remove(view.cloud); view.cloud.userData.dispose?.(); }
            view.cloud = null; view.frame = null;
            view.element.querySelector('.viewer-message').hidden = false;
            view.element.querySelector('.viewer-message').textContent = 'Preview unavailable';
        }
        ownedGeometries.forEach(geometry => geometry.dispose());
        status.textContent = 'The method preview could not load. Reload the page to retry.';
        render();
        console.error(error);
    }
}

slider.addEventListener('input', () => {
    const size = Number(slider.value);
    root.querySelector('output').textContent = `${size} px`;
    views.filter(view => !view.panel.voxels).forEach(view => pointSize(view.material, size, view.renderer));
    render();
});
resetButton.addEventListener('click', reset);
if ('IntersectionObserver' in globalThis) {
    const observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) { observer.disconnect(); start(); }
    }, {rootMargin: '300px'});
    observer.observe(root);
} else {
    start();
}
