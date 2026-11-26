import {readAsset} from './lib/assets.js';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {PLYLoader} from 'three/addons/loaders/PLYLoader.js';
import {createRenderer, synchronize, pointSize} from './lib/runtime.js';
import {createPointMaterials, preparePointGeometry} from './lib/points.js';

const methods = [['vsurf_final','VSurf'], ['vggt_omega','VGGT-omega'], ['surflo_plain','Surflo']];
const scenes = {stadium:['Stadium',128], counter:['Counter',16], green_room:['Green Room',100],
  garden:['Garden',16], pyramid:['Pyramid',16], valley:['Valley',11], rubble:['Rubble',256],
  '1ada7a0617':['ScanNet++ 1ada7a0617',100,100000], staircase:['Staircase',100,100000],
  scan114:['DTU 114',49,100000], scan23:['DTU 23',49,100000]};
const assetVersion = 'all-scenes-100k-v8';
const views = [], loader = new PLYLoader(), status = document.querySelector('#status');
const sceneGeometries = new Map();
let mode = 'rgb', version = 0, frame = null;
const render = () => views.forEach(v => v.renderer.render(v.scene, v.camera));
const size = () => Number(document.querySelector('#point-size').value);

function reset() {
  if (!frame) return;
  const radius = Math.max(frame.radius, .001);
  for (const v of views) {
    const halfFov = THREE.MathUtils.degToRad(v.camera.fov / 2);
    const fitAngle = Math.min(halfFov, Math.atan(Math.tan(halfFov) * v.camera.aspect));
    const distance = radius / Math.sin(fitAngle) * 0.625;
    v.camera.position.copy(frame.center).add(new THREE.Vector3(0,0,distance));
    v.controls.target.copy(frame.center);
    v.camera.near = radius / 1000; v.camera.far = radius * 1000;
    v.controls.minDistance = radius * .01; v.controls.maxDistance = radius * 100;
    v.camera.updateProjectionMatrix(); v.controls.update();
  }
  render();
}

function setup() {
  for (const [id,label] of methods) {
    const element = document.createElement('article'); element.className = 'panel';
    element.innerHTML = `<header><h3>${label}</h3></header><div class="viewport"><span class="viewer-message">Loading…</span></div>`;
    document.querySelector('#panels').append(element);
    const viewport = element.querySelector('.viewport');
    const renderer = createRenderer({background:0xf4f6fa}); viewport.prepend(renderer.domElement);
    renderer.domElement.setAttribute('aria-label', `${label} interactive point cloud`);
    const camera = new THREE.PerspectiveCamera(45, 4/3, .001, 1000);
    camera.position.set(0,0,5);
    // Use the same unmodified OrbitControls defaults as viewers/shared/comparison.js.
    const controls = new OrbitControls(camera, renderer.domElement);
    const v = {id, element, renderer, camera, controls, scene:new THREE.Scene(), materials:createPointMaterials(), cloud:null};
    views.push(v);
    new ResizeObserver(() => {
      const {width,height} = viewport.getBoundingClientRect();
      if (!width || !height) return;
      renderer.setSize(width,height,false); camera.aspect = width/height; camera.updateProjectionMatrix(); render();
    }).observe(viewport);
    renderer.domElement.addEventListener('webglcontextlost', event => {
      event.preventDefault(); const message = element.querySelector('.viewer-message');
      message.hidden = false; message.textContent = 'Graphics context lost. Reload to continue.';
    });
  }
  synchronize(views,render);
}

async function loadScene(scene) {
  const request = ++version; frame = null;
  const [, inputFrames, pointCount = 100000] = scenes[scene];
  document.querySelectorAll('[data-scene]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.scene === scene)));
  status.textContent = 'Loading…';
  for (const v of views) {
    if (v.cloud) {v.scene.remove(v.cloud); v.cloud = null;}
    const message = v.element.querySelector('.viewer-message'); message.hidden = false; message.textContent = 'Loading…';
  }
  for (const geometry of sceneGeometries.values()) geometry.dispose();
  sceneGeometries.clear();
  render();
  const results = await Promise.allSettled([
    readAsset(`./assets/${scene}/inputs.json?v=${assetVersion}`, {json:true}),
    ...methods.map(([id]) => readAsset(`./assets/${scene}/${id}.ply?v=${assetVersion}`).then(bytes => loader.parse(bytes)))
  ]);
  if (request !== version) {results.slice(1).forEach(r => {if(r.status === 'fulfilled') r.value.dispose();}); return;}
  if (results.some(r => r.status === 'rejected')) {
    results.slice(1).forEach(r => {if(r.status === 'fulfilled') r.value.dispose();});
    status.textContent = 'Scene could not load. Select it to retry.';
    for (const v of views) v.element.querySelector('.viewer-message').textContent = 'Scene assets unavailable. Select the scene to retry.';
    return;
  }
  const geometries = results.slice(1).map(r => r.value);
  try {
    const metadata = results[0].value;
    if (metadata.input_frames !== inputFrames || metadata.frames.length !== inputFrames) throw new Error(`Expected ${inputFrames} input views`);
    if (metadata.point_count !== pointCount) throw new Error('Scene point budget mismatch');
    // Match viewers/wild inputCameraView: rotate the shared COLMAP frame into
    // first-camera coordinates with Y up and forward -Z. OrbitControls caches
    // its up axis on construction, so camera.up must stay at its default.
    const pose = metadata.frames[0].c2w;
    const rows = metadata.display_rotation || [0,1,2].map(axis => [0,1,2].map(row => pose[row][axis] * (axis === 0 ? 1 : -1)));
    const displayRotation = new THREE.Matrix4().set(
      ...rows[0],0, ...rows[1],0, ...rows[2],0, 0,0,0,1);
    const bounds = new THREE.Box3();
    for (const [index, geometry] of geometries.entries()) {
      preparePointGeometry(geometry, {rotationX:0});
      if (geometry.attributes.position.count !== pointCount) throw new Error('Point count does not match scene metadata');
      geometry.applyMatrix4(displayRotation);
      // Match the Wild viewer framing, which compares VSurf and VGGT-omega.
      if (methods[index][0] !== 'surflo_plain') bounds.union(geometry.boundingBox);
    }
    frame = bounds.getBoundingSphere(new THREE.Sphere());
    methods.forEach(([id], i) => sceneGeometries.set(id, geometries[i]));
    for (let i=0;i<views.length;i++) {
      const v = views[i];
      for (const material of Object.values(v.materials)) pointSize(material,size(),v.renderer);
      v.cloud = new THREE.Points(sceneGeometries.get(v.id),v.materials[mode]); v.scene.add(v.cloud);
      v.element.querySelector('.viewer-message').hidden = true;
    }
    reset(); status.textContent = '';
  } catch (error) {
    for (const v of views) {if(v.cloud) v.scene.remove(v.cloud); v.cloud = null; const message=v.element.querySelector('.viewer-message');message.hidden=false;message.textContent=error.message;}
    geometries.forEach(g => g.dispose()); sceneGeometries.clear(); frame = null; status.textContent = 'Scene assets are invalid.'; render();
  }
}

document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => {
  mode = button.dataset.mode;
  document.querySelectorAll('[data-mode]').forEach(b => b.setAttribute('aria-pressed',String(b === button)));
  for (const v of views) if(v.cloud) v.cloud.material = v.materials[mode];
  render();
}));
const sceneButtons = document.querySelectorAll('[data-scene]');
sceneButtons.forEach(button => button.addEventListener('click', () => loadScene(button.dataset.scene)));
document.querySelector('#point-size').addEventListener('input', () => {
  document.querySelector('#point-size-value').textContent = `${size()} px`;
  for (const v of views) for (const material of Object.values(v.materials)) pointSize(material,size(),v.renderer);
  render();
});
document.querySelector('#reset').addEventListener('click',reset);
try {setup(); loadScene(sceneButtons[0].dataset.scene);} catch(error) {status.textContent='WebGL could not start. Use a browser with hardware acceleration enabled.';}
