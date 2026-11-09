
export const WIDTH = 10;
export const HEIGHT = 22;
export const VISIBLE_HEIGHT = 20;
export const TYPES = ['I', 'O', 'T', 'S', 'Z', 'J', 'L'];

export const SHAPES = {
I: [[0,1],[1,1],[2,1],[3,1]],
O: [[1,0],[2,0],[1,1],[2,1]],
T: [[1,0],[0,1],[1,1],[2,1]],
S: [[1,0],[2,0],[0,1],[1,1]],
Z: [[0,0],[1,0],[1,1],[2,1]],
J: [[0,0],[0,1],[1,1],[2,1]],
L: [[2,0],[0,1],[1,1],[2,1]]
};

export const COLORS = {
I: 0x32e9ff, O: 0xffd84d, T: 0xb17aff,
S: 0x49ffb3, Z: 0xff547e, J: 0x638aff, L: 0xffa54d
};

const JL_KICKS = {
'0>1': [[0,0],[-1,0],[-1,-1],[0,2],[-1,2]],
'1>0': [[0,0],[1,0],[1,1],[0,-2],[1,-2]],
'1>2': [[0,0],[1,0],[1,1],[0,-2],[1,-2]],
'2>1': [[0,0],[-1,0],[-1,-1],[0,2],[-1,2]],
'2>3': [[0,0],[1,0],[1,-1],[0,2],[1,2]],
'3>2': [[0,0],[-1,0],[-1,1],[0,-2],[-1,-2]],
'3>0': [[0,0],[-1,0],[-1,1],[0,-2],[-1,-2]],
'0>3': [[0,0],[1,0],[1,-1],[0,2],[1,2]]
};
const I_KICKS = {
'0>1': [[0,0],[-2,0],[1,0],[-2,1],[1,-2]],
'1>0': [[0,0],[2,0],[-1,0],[2,-1],[-1,2]],
'1>2': [[0,0],[-1,0],[2,0],[-1,-2],[2,1]],
'2>1': [[0,0],[1,0],[-2,0],[1,2],[-2,-1]],
'2>3': [[0,0],[2,0],[-1,0],[2,-1],[-1,2]],
'3>2': [[0,0],[-2,0],[1,0],[-2,1],[1,-2]],
'3>0': [[0,0],[1,0],[-2,0],[1,2],[-2,-1]],
'0>3': [[0,0],[-1,0],[2,0],[-1,-2],[2,1]]
};

export function shuffledBag(random = Math.random) {
const bag = [...TYPES];
for (let i = bag.length - 1; i > 0; i--) {
const j = Math.floor(random() * (i + 1));
[bag[i], bag[j]] = [bag[j], bag[i]];
}
return bag;
}

export function rotateCells(cells, direction, type) {
if (type === 'O') return cells.map(c => [...c]);
return cells.map(([x,y]) => direction === 1 ? [3-y,x] : [y,3-x]);
}

export class Game {
constructor(random = Math.random) {
this.random = random;
this.reset();
}

reset() {
this.board = Array.from({length: HEIGHT}, () => Array(WIDTH).fill(null));
this.queue = [];
this.active = null;
this.holdType = null;
this.canHold = true;
this.score = 0;
this.lines = 0;
this.level = 1;
this.combo = -1;
this.backToBack = false;
this.over = false;
this.paused = false;
this.fallTimer = 0;
this.lockTimer = 0;
this.lockResets = 0;
this.lastEvent = '';
this.fillQueue();
this.spawn();
}

fillQueue() {
while (this.queue.length < 7) this.queue.push(...shuffledBag(this.random));
}

spawn(type = null) {
this.fillQueue();
const next = type || this.queue.shift();
this.fillQueue();
this.active = {type: next, cells: SHAPES[next].map(c => [...c]), x: 3, y: -1, rotation: 0, lastRotate: false};
this.fallTimer = 0;
this.lockTimer = 0;
this.lockResets = 0;
if (!this.valid(this.active)) this.over = true;
}

valid(piece) {
return piece.cells.every(([dx,dy]) => {
const x = piece.x + dx, y = piece.y + dy;
return x >= 0 && x < WIDTH && y < HEIGHT && (y < 0 || !this.board[y][x]);
});
}

move(dx, dy, user = true) {
if (this.over || this.paused) return false;
const candidate = {...this.active, x: this.active.x + dx, y: this.active.y + dy};
if (!this.valid(candidate)) return false;
this.active = {...candidate, lastRotate: false};
if (user && dy > 0) this.score += dy;
if (user && dx) this.resetLock();
return true;
}

resetLock() {
if (this.lockResets < 15) {
this.lockTimer = 0;
this.lockResets++;
}
}

rotate(direction = 1) {
if (this.over || this.paused) return false;
const p = this.active;
const nextRotation = (p.rotation + direction + 4) % 4;
const cells = rotateCells(p.cells, direction, p.type);
const kicks = p.type === 'O' ? [[0,0]] : (p.type === 'I' ? I_KICKS : JL_KICKS)[`${p.rotation}>${nextRotation}`];
for (const [dx,dy] of kicks) {
const candidate = {...p, cells, rotation: nextRotation, x: p.x + dx, y: p.y - dy, lastRotate: true};
if (this.valid(candidate)) {
this.active = candidate;
this.resetLock();
return true;
}
}
return false;
}

ghostY() {
let y = this.active.y;
while (this.valid({...this.active, y: y + 1})) y++;
return y;
}

hardDrop() {
if (this.over || this.paused) return;
const distance = this.ghostY() - this.active.y;
this.active.y += distance;
this.score += distance * 2;
this.lock();
}

hold() {
if (this.over || this.paused || !this.canHold) return false;
const previous = this.holdType;
this.holdType = this.active.type;
this.spawn(previous);
this.canHold = false;
return true;
}

isTSpin() {
const p = this.active;
if (p.type !== 'T' || !p.lastRotate) return false;
const cx = p.x + 1, cy = p.y + 1;
let occupied = 0;
for (const [dx,dy] of [[-1,-1],[1,-1],[-1,1],[1,1]]) {
const x = cx + dx, y = cy + dy;
if (x < 0 || x >= WIDTH || y >= HEIGHT || (y >= 0 && this.board[y][x])) occupied++;
}
return occupied >= 3;
}

lock() {
if (this.over) return;
const spin = this.isTSpin();
for (const [dx,dy] of this.active.cells) {
const x = this.active.x + dx, y = this.active.y + dy;
if (y < 0) {
this.over = true;
return;
}
this.board[y][x] = this.active.type;
}
const remaining = this.board.filter(row => row.some(cell => !cell));
const cleared = HEIGHT - remaining.length;
while (remaining.length < HEIGHT) remaining.unshift(Array(WIDTH).fill(null));
this.board = remaining;
const base = spin ? [400,800,1200,1600][cleared] : [0,100,300,500,800][cleared];
const difficult = (cleared === 4 || (spin && cleared > 0));
const bonus = difficult && this.backToBack ? 1.5 : 1;
if (cleared) {
this.combo++;
this.score += Math.round(base * this.level * bonus) + Math.max(0,this.combo) * 50 * this.level;
this.lines += cleared;
this.level = 1 + Math.floor(this.lines / 10);
if (difficult) this.backToBack = true;
else this.backToBack = false;
this.lastEvent = spin ? `T-SPIN · ${cleared} LINE` : cleared === 4 ? 'TETRIS!' : `${cleared} LINE${cleared > 1 ? 'S' : ''} CLEARED`;
} else {
this.combo = -1;
this.lastEvent = spin ? 'T-SPIN' : 'LOCK';
}
this.canHold = true;
this.spawn();
}

step(dt) {
if (this.over || this.paused) return;
const interval = Math.max(65, 850 * Math.pow(0.82, this.level - 1));
this.fallTimer += dt;
while (this.fallTimer >= interval) {
this.fallTimer -= interval;
if (!this.move(0,1,false)) break;
}
if (!this.valid({...this.active, y: this.active.y + 1})) {
this.lockTimer += dt;
if (this.lockTimer >= 500) this.lock();
} else {
this.lockTimer = 0;
}
}
}
