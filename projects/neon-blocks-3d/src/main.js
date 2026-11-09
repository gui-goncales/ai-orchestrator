
import * as THREE from 'three';
import { Game, WIDTH, VISIBLE_HEIGHT, SHAPES, COLORS } from './core.js';
import './style.css';

const game = new Game();
const app = document.querySelector('#app');
app.innerHTML = `
<div class="shell">
<header class="topbar">
<div class="brand"><span class="brand-icon">◈</span><div><small>THE FUTURE OF ARCADE</small><h1>NEON <em>BLOCKS</em> <span>3D</span></h1></div></div>
<div class="top-actions"><span class="mode-tag">◉ MARATHON MODE</span><button id="sound" class="icon-btn" aria-label="Toggle sound">♫</button><button id="pause" class="icon-btn" aria-label="Pause">Ⅱ</button></div>
</header>
<main class="layout">
<aside class="left">
<div class="panel hold-panel"><div class="panel-label">HOLD <span>01</span></div><div id="hold-piece" class="mini-piece"></div><div class="panel-hint">C / SHIFT</div></div>
<div class="panel info-panel"><div class="panel-label">HOW TO PLAY</div><div class="keyrow"><kbd>←</kbd><kbd>→</kbd><span>MOVE</span></div><div class="keyrow"><kbd>↑</kbd><span>ROTATE</span></div><div class="keyrow"><kbd>SPACE</kbd><span>DROP</span></div><div class="keyrow"><kbd>C</kbd><span>HOLD</span></div></div>
<div class="decorative"><span>◆</span> BUILT FOR THE FLOW STATE</div>
</aside>
<section class="game-area"><div class="board-heading"><span>◈ NEON ARENA</span><span class="live">● LIVE SESSION</span></div><div id="stage"></div><div class="board-footer"><span>GRID 10 × 20</span><span>◉ SYSTEM ONLINE</span></div></section>
<aside class="right">
<div class="panel score-panel"><div class="panel-label">TOTAL SCORE <span>↗</span></div><strong id="score">000,000</strong><div class="best">PERSONAL BEST <span id="best">0</span></div></div>
<div class="stat-grid"><div class="panel stat"><div class="panel-label">LEVEL</div><strong id="level">01</strong></div><div class="panel stat"><div class="panel-label">LINES</div><strong id="lines">00</strong></div></div>
<div class="panel next-panel"><div class="panel-label">UP NEXT <span>05</span></div><div id="next-pieces"></div></div>
<div class="panel combo-panel"><div class="panel-label">COMBO CHAIN</div><strong id="combo">—</strong></div>
</aside>
</main>
<div class="touch-controls"><button data-action="left">◀</button><button data-action="rotate">↻</button><button data-action="right">▶</button><button data-action="down">▼</button><button data-action="hold">HOLD</button><button data-action="drop">DROP</button></div>
<footer class="footer"><span>NEON BLOCKS 3D <i>●</i> V0.1</span><span>PRECISION. RHYTHM. FLOW.</span><span>DESIGNED FOR THE NEXT LEVEL</span></footer>
</div>
<div id="overlay" class="overlay"><div class="modal"><div class="modal-symbol">◈</div><small>ENTER THE ARENA</small><h2 id="modal-title">NEON<br><span>BLOCKS 3D</span></h2><p id="modal-desc">Stack. Clear. Ascend.<br>Experience the next generation of falling blocks.</p><button id="play" class="primary">START GAME <span>→</span></button><div class="modal-foot">PRESS ENTER TO START</div></div></div>
<div id="toast"></div>
`;

const stage = document.querySelector('#stage');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x080e22);
scene.fog = new THREE.FogExp2(0x080e22, 0.019);
const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
camera.position.set(0, 0, 34);
camera.lookAt(0, 0, 0);
const renderer = new THREE.WebGLRenderer({antialias: true, alpha: false});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.4;
stage.appendChild(renderer.domElement);

const ambient = new THREE.AmbientLight(0x7899ff, 1.4);
scene.add(ambient);
const keyLight = new THREE.PointLight(0x00d9ff, 90, 45);
keyLight.position.set(-7, 9, 12);
scene.add(keyLight);
const fillLight = new THREE.PointLight(0x925cff, 75, 40);
fillLight.position.set(8, -7, 9);
scene.add(fillLight);

const boardGroup = new THREE.Group();
scene.add(boardGroup);
const backing = new THREE.Mesh(new THREE.BoxGeometry(10.6, 20.6, 0.4), new THREE.MeshStandardMaterial({color:0x0a1630, metalness:0.6, roughness:0.35}));
backing.position.z = -0.45;
boardGroup.add(backing);

const frameMaterial = new THREE.MeshStandardMaterial({color:0x17c8f5, emissive:0x056a95, emissiveIntensity:0.65, metalness:0.8, roughness:0.2});
const frameParts = [[10.7,0.09,0,-10.35],[10.7,0.09,0,10.35],[0.09,20.7,-5.35,0],[0.09,20.7,5.35,0]];
for (const [w,h,x,y] of frameParts) {
const mesh = new THREE.Mesh(new THREE.BoxGeometry(w,h,0.28),frameMaterial);
mesh.position.set(x,y,0);
boardGroup.add(mesh);
}
const gridMaterial = new THREE.LineBasicMaterial({color:0x1c365a,transparent:true,opacity:0.42});
const vertices = [];
for(let x=0;x<=WIDTH;x++) vertices.push(x-5,-10,0, x-5,10,0);
for(let y=0;y<=VISIBLE_HEIGHT;y++) vertices.push(-5,y-10,0, 5,y-10,0);
const gridGeometry = new THREE.BufferGeometry();
gridGeometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
const gridLines = new THREE.LineSegments(gridGeometry,gridMaterial);
gridLines.position.z = -0.17;
boardGroup.add(gridLines);

const geometry = new THREE.BoxGeometry(0.89,0.89,0.72);
const edgeGeometry = new THREE.EdgesGeometry(new THREE.BoxGeometry(0.91,0.91,0.74));
const materials = {};
const edgeMaterials = {};
for(const [type,color] of Object.entries(COLORS)) {
materials[type] = new THREE.MeshPhysicalMaterial({color,metalness:0.28,roughness:0.19,clearcoat:1,clearcoatRoughness:0.12,emissive:color,emissiveIntensity:0.25});
edgeMaterials[type] = new THREE.LineBasicMaterial({color,transparent:true,opacity:0.72});
}
const ghostMaterial = new THREE.MeshBasicMaterial({color:0x4b8da9,transparent:true,opacity:0.16,depthWrite:false});
const ghostEdges = new THREE.LineBasicMaterial({color:0x5ee5ff,transparent:true,opacity:0.37});
const blocks = Array.from({length:220},()=> {
const group = new THREE.Group();
const mesh = new THREE.Mesh(geometry,materials.I);
const edges = new THREE.LineSegments(edgeGeometry,edgeMaterials.I);
group.add(mesh,edges);
boardGroup.add(group);
return {group,mesh,edges};
});
const ghostBlocks = Array.from({length:4},()=>{
const group = new THREE.Group();
group.add(new THREE.Mesh(geometry,ghostMaterial),new THREE.LineSegments(edgeGeometry,ghostEdges));
boardGroup.add(group);
return group;
});

const starsGeometry = new THREE.BufferGeometry();
const starCoords = [];
for(let i=0;i<220;i++) starCoords.push((Math.random()-0.5)*38,(Math.random()-0.5)*36,-4-Math.random()*18);
starsGeometry.setAttribute('position',new THREE.Float32BufferAttribute(starCoords,3));
const stars = new THREE.Points(starsGeometry,new THREE.PointsMaterial({color:0x77bfff,size:0.045,transparent:true,opacity:0.65}));
scene.add(stars);

function place(group,x,y) {
group.position.set(x-4.5,9.5-y,0.35);
group.visible = y>=0 && y<VISIBLE_HEIGHT;
}
function drawBoard() {
let index=0;
for(let y=2;y<22;y++) for(let x=0;x<10;x++) {
const type=game.board[y][x];
if(!type) continue;
const block=blocks[index++];
block.mesh.material=materials[type];
block.edges.material=edgeMaterials[type];
place(block.group,x,y-2);
}
if(!game.over) {
for(const [dx,dy] of game.active.cells) {
const block=blocks[index++];
block.mesh.material=materials[game.active.type];
block.edges.material=edgeMaterials[game.active.type];
place(block.group,game.active.x+dx,game.active.y+dy-2);
}
const gy=game.ghostY();
game.active.cells.forEach(([dx,dy],i)=>place(ghostBlocks[i],game.active.x+dx,gy+dy-2));
} else ghostBlocks.forEach(g=>g.visible=false);
for(;index<blocks.length;index++) blocks[index].group.visible=false;
}

function mini(type) {
if(!type) return '<span class="empty">EMPTY</span>';
const cells=SHAPES[type];
const minX=Math.min(...cells.map(c=>c[0])),maxX=Math.max(...cells.map(c=>c[0]));
const minY=Math.min(...cells.map(c=>c[1])),maxY=Math.max(...cells.map(c=>c[1]));
return `<div class="mini-grid" style="grid-template-columns:repeat(${maxX-minX+1}, 17px)">${cells.map(()=> '').join('')}${Array.from({length:(maxY-minY+1)*(maxX-minX+1)},(_,i)=>{
const x=i%(maxX-minX+1)+minX,y=Math.floor(i/(maxX-minX+1))+minY;
return `<div class="mini-cell ${cells.some(([cx,cy])=>cx===x&&cy===y)?'filled':''}" style="--piece:${'#'+COLORS[type].toString(16).padStart(6,'0')}"></div>`;
}).join('')}</div>`;
}
function updateHud() {
document.querySelector('#score').textContent=game.score.toLocaleString('en-US').padStart(7,'0');
document.querySelector('#level').textContent=String(game.level).padStart(2,'0');
document.querySelector('#lines').textContent=String(game.lines).padStart(2,'0');
document.querySelector('#combo').textContent=game.combo>0?`×${game.combo+1}`:'—';
document.querySelector('#hold-piece').innerHTML=mini(game.holdType);
document.querySelector('#next-pieces').innerHTML=game.queue.slice(0,5).map((type,i)=>`<div class="next-item"><span>${String(i+1).padStart(2,'0')}</span>${mini(type)}</div>`).join('');
document.querySelector('#best').textContent=best.toLocaleString('en-US');
}
let best=0;
try {best=Number(localStorage.getItem('neon-blocks-best'))||0;} catch {}
let started=false;
let soundOn=true;
let audioContext;
function sound(freq=440,duration=0.07,type='sine') {
if(!soundOn) return;
try {
audioContext ||= new (window.AudioContext||window.webkitAudioContext)();
const osc=audioContext.createOscillator(),gain=audioContext.createGain();
osc.type=type; osc.frequency.setValueAtTime(freq,audioContext.currentTime);
osc.frequency.exponentialRampToValueAtTime(Math.max(50,freq*0.65),audioContext.currentTime+duration);
gain.gain.setValueAtTime(0.045,audioContext.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,audioContext.currentTime+duration);
osc.connect(gain).connect(audioContext.destination);
osc.start();osc.stop(audioContext.currentTime+duration);
} catch {}
}
function showOverlay(title,desc,button) {
document.querySelector('#modal-title').innerHTML=title;
document.querySelector('#modal-desc').innerHTML=desc;
document.querySelector('#play').innerHTML=button+' <span>→</span>';
document.querySelector('#overlay').classList.remove('hidden');
}
function start() {
if(!started || game.over) game.reset();
game.paused=false;started=true;
document.querySelector('#overlay').classList.add('hidden');
updateHud();
sound(620,0.16);
}
function pause() {
if(!started||game.over)return;
game.paused=!game.paused;
if(game.paused)showOverlay('GAME <span>PAUSED</span>','Take a moment. Your arena is waiting.','RESUME GAME');
else document.querySelector('#overlay').classList.add('hidden');
}
document.querySelector('#play').onclick=start;
document.querySelector('#pause').onclick=pause;
document.querySelector('#sound').onclick=()=>{soundOn=!soundOn;document.querySelector('#sound').style.opacity=soundOn?'1':'.35';};
function action(name) {
if(!started||game.over||game.paused)return;
if(name==='left'&&game.move(-1,0))sound(220,0.035);
if(name==='right'&&game.move(1,0))sound(250,0.035);
if(name==='down'&&game.move(0,1))sound(160,0.035);
if(name==='rotate'&&game.rotate())sound(460,0.07);
if(name==='counter'&&game.rotate(-1))sound(400,0.07);
if(name==='drop'){game.hardDrop();sound(95,0.15,'triangle');}
if(name==='hold'&&game.hold())sound(340,0.1);
updateHud();
}
const keyMap={ArrowLeft:'left',ArrowRight:'right',ArrowDown:'down',ArrowUp:'rotate',KeyX:'rotate',KeyZ:'counter',Space:'drop',KeyC:'hold',ShiftLeft:'hold',ShiftRight:'hold'};
document.addEventListener('keydown',e=>{
if(['ArrowLeft','ArrowRight','ArrowDown','ArrowUp','Space'].includes(e.code))e.preventDefault();
if(e.code==='Enter'&&(!started||game.over||game.paused)){start();return;}
if(e.code==='Escape'||e.code==='KeyP'){pause();return;}
if(e.repeat&&['Space','KeyC','ShiftLeft','ShiftRight','ArrowUp','KeyX','KeyZ'].includes(e.code))return;
if(keyMap[e.code])action(keyMap[e.code]);
});
document.querySelectorAll('[data-action]').forEach(btn=>{
btn.addEventListener('pointerdown',e=>{e.preventDefault();action(btn.dataset.action);});
});
let touchStart=null;
stage.addEventListener('pointerdown',e=>{touchStart={x:e.clientX,y:e.clientY};});
stage.addEventListener('pointerup',e=>{
if(!touchStart)return;
const dx=e.clientX-touchStart.x,dy=e.clientY-touchStart.y;
if(Math.abs(dx)<20&&Math.abs(dy)<20)action('rotate');
else if(Math.abs(dy)>65&&dy>0)action('drop');
else if(Math.abs(dx)>25)for(let i=0;i<Math.min(5,Math.floor(Math.abs(dx)/35));i++)action(dx>0?'right':'left');
else if(dy>20)action('down');
touchStart=null;
});
function resize() {
const w=stage.clientWidth,h=stage.clientHeight;
renderer.setSize(w,h,false);
camera.aspect=w/h;
camera.position.z=Math.max(29, 21/(2*Math.tan(THREE.MathUtils.degToRad(camera.fov/2))) / camera.aspect * 0.65);
camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(stage);
resize();
let previous=performance.now(),accumulator=0,lastEvent='';
function frame(now) {
const dt=Math.min(now-previous,100);
previous=now;
if(started&&!game.paused&&!game.over) {
accumulator+=dt;
while(accumulator>=1000/60){game.step(1000/60);accumulator-=1000/60;}
if(game.lastEvent!==lastEvent) {
lastEvent=game.lastEvent;
if(lastEvent.includes('LINE')||lastEvent.includes('TETRIS')){
const toast=document.querySelector('#toast');toast.textContent=lastEvent;toast.classList.add('show');
setTimeout(()=>toast.classList.remove('show'),850);
sound(lastEvent==='TETRIS!'?820:590,0.23,'triangle');
}
}
if(game.score>best){best=game.score;try{localStorage.setItem('neon-blocks-best',String(best));}catch{}}
updateHud();
if(game.over){showOverlay('GAME <span>OVER</span>',`FINAL SCORE · ${game.score.toLocaleString('en-US')}<br>Every ending is a new beginning.`,'PLAY AGAIN');sound(110,0.35);}
}
drawBoard();
stars.rotation.z=Math.sin(now*0.00008)*0.02;
renderer.render(scene,camera);
requestAnimationFrame(frame);
}
updateHud();
requestAnimationFrame(frame);
