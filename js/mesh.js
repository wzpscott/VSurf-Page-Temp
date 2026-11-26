import {readAsset} from './lib/assets.js';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {PLYLoader} from 'three/addons/loaders/PLYLoader.js';
import {createRenderer, synchronize} from './lib/runtime.js';

const root = document.querySelector('#mesh-reconstruction');
const status = root.querySelector('[role="status"]');
const panelLabels = ['Colored Mesh','Surface','Normals'];
const views = [], loader = new PLYLoader();
let geometry = null, frame = null, version = 0, started = false;
const render = () => views.forEach(v => v.renderer.render(v.scene, v.camera));

export function validateGeometry(g, metadata) {
  const p = g.getAttribute('position'), n = g.getAttribute('normal'), c = g.getAttribute('color');
  if (!p?.count || p.count !== metadata.vertices ||
      n?.count !== p.count || c?.count !== p.count || !g.index?.count ||
      g.index.count > 500000 * 3 || g.index.count !== metadata.triangles * 3) throw new Error('Invalid mesh counts or attributes');
  for (const a of [p,n,c]) if (!a.array.every(Number.isFinite)) throw new Error('Invalid mesh attributes');
  for (const i of g.index.array) if (i < 0 || i >= p.count) throw new Error('Invalid mesh indices');
}

function reset() {
  if (!frame) return;
  const radius = Math.max(frame.radius, .001);
  const aspect = Math.min(...views.map(v => v.camera.aspect));
  const angle = Math.min(Math.PI/8, Math.atan(Math.tan(Math.PI/8)*aspect));
  for (const v of views) {
    v.camera.position.copy(frame.center).add(new THREE.Vector3(0,0,radius/Math.sin(angle)*.625));
    v.controls.target.copy(frame.center);
    v.camera.near = radius/1000; v.camera.far = radius*1000;
    v.controls.minDistance = radius*.01; v.controls.maxDistance = radius*100;
    v.camera.updateProjectionMatrix(); v.controls.update();
  }
  render();
}

function setup() {
  const materials = [
    new THREE.MeshBasicMaterial({vertexColors:true, side:THREE.DoubleSide, toneMapped:false}),
    new THREE.MeshStandardMaterial({color:0xc3c9cf, roughness:.8, metalness:0, side:THREE.DoubleSide}),
    new THREE.MeshNormalMaterial({side:THREE.DoubleSide})
  ];
  panelLabels.forEach((label,i) => {
    const element = document.createElement('article'); element.className = 'panel';
    element.innerHTML = `<header><h3>${label}</h3></header><div class="viewport"><span class="viewer-message">Loading…</span></div>`;
    root.querySelector('.mesh-panels').append(element);
    const viewport = element.querySelector('.viewport');
    const renderer = createRenderer({background:0xffffff}); viewport.prepend(renderer.domElement);
    renderer.domElement.setAttribute('aria-label', `${label} interactive reconstruction`);
    const camera = new THREE.PerspectiveCamera(45,4/3,.001,1000);
    const controls = new OrbitControls(camera,renderer.domElement), scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff,0x687680,2.4));
    const light = new THREE.DirectionalLight(0xffffff,2); light.position.set(2,4,3); scene.add(light);
    const v = {element,renderer,camera,controls,scene,material:materials[i],object:null}; views.push(v);
    new ResizeObserver(() => {
      const {width,height} = viewport.getBoundingClientRect(); if (!width || !height) return;
      renderer.setSize(width,height,false); camera.aspect = width/height; camera.updateProjectionMatrix(); render();
    }).observe(viewport);
    renderer.domElement.addEventListener('webglcontextlost', event => {
      event.preventDefault(); v.contextLost=true;
      const message=element.querySelector('.viewer-message');
      message.hidden=false; message.textContent='Graphics context lost. Reload to continue.';
    });
  });
  synchronize(views,render);
}

async function loadScene(name) {
  const request = ++version; frame = null;
  root.querySelectorAll('[data-mesh-scene]').forEach(b => b.setAttribute('aria-pressed',String(b.dataset.meshScene===name)));
  status.textContent='Loading…';
  for (const v of views) {
    if (v.object) v.scene.remove(v.object); v.object=null;
    const message=v.element.querySelector('.viewer-message'); message.hidden=false; message.textContent='Loading…';
  }
  geometry?.dispose(); geometry=null; render();
  let loaded=null;
  try {
    const [bytes,metadata,inputs] = await Promise.all([
      readAsset(`./assets/mesh/${name}/mesh.ply`),
      readAsset(`./assets/mesh/${name}/metadata.json`,{json:true}),
      readAsset(`./assets/${name}/inputs.json`,{json:true})
    ]);
    if (request!==version) return;
    loaded=loader.parse(bytes); validateGeometry(loaded,metadata);
    const pose=inputs.frames[0].c2w;
    const rows=inputs.display_rotation || [0,1,2].map(axis => [0,1,2].map(row => pose[row][axis]*(axis===0?1:-1)));
    loaded.applyMatrix4(new THREE.Matrix4().set(...rows[0],0,...rows[1],0,...rows[2],0,0,0,0,1));
    loaded.computeBoundingBox(); loaded.computeBoundingSphere();
    geometry=loaded; frame=geometry.boundingSphere;
    for (const v of views) {
      v.object=new THREE.Mesh(geometry,v.material); v.scene.add(v.object);
      v.element.querySelector('.viewer-message').hidden=true;
    }
    reset();
    status.textContent='';
  } catch(error) {
    loaded?.dispose();
    if (request!==version) return;
    geometry=null; frame=null;
    for (const v of views) {
      if(v.object) v.scene.remove(v.object); v.object=null;
      const message=v.element.querySelector('.viewer-message');message.hidden=false;
      message.textContent='Mesh unavailable. Select the scene to retry.';
    }
    status.textContent='Mesh could not load. Select the scene to retry.'; render();
  }
}

function start() {
  if (started) return;
  started=true;
  try {
    setup();
    const sceneButtons = root.querySelectorAll('[data-mesh-scene]');
    sceneButtons.forEach(b => b.addEventListener('click',()=>loadScene(b.dataset.meshScene)));
    return loadScene(sceneButtons[0].dataset.meshScene);
  } catch(error) {status.textContent='WebGL could not start. Use a browser with hardware acceleration enabled.';}
}
if ('IntersectionObserver' in globalThis) {
  const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();start();}}, {rootMargin:'300px'});
  observer.observe(root);
} else start();
