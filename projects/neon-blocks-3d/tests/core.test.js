
import {describe,it,expect} from 'vitest';
import {Game,WIDTH,HEIGHT,TYPES,SHAPES,shuffledBag} from '../src/core.js';

describe('NEON BLOCKS engine',()=>{
it('creates a 10x22 board with 20 visible rows',()=>{
const g=new Game();
expect(g.board).toHaveLength(HEIGHT);
expect(g.board[0]).toHaveLength(WIDTH);
});
it('all seven tetrominoes contain exactly four cells',()=>{
expect(TYPES).toHaveLength(7);
for(const type of TYPES)expect(SHAPES[type]).toHaveLength(4);
});
it('7-bag produces all seven types once',()=>{
expect(new Set(shuffledBag(()=>0.5)).size).toBe(7);
});
it('cannot move outside board',()=>{
const g=new Game();
for(let i=0;i<20;i++)g.move(-1,0);
expect(g.move(-1,0)).toBe(false);
});
it('hard drop locks a piece and creates a new one',()=>{
const g=new Game();
const first=g.active.type;
g.hardDrop();
expect(g.board.flat().filter(Boolean)).toHaveLength(4);
expect(g.active).not.toBeNull();
expect(g.score).toBeGreaterThanOrEqual(0);
});
it('hold is allowed once per piece',()=>{
const g=new Game();
expect(g.hold()).toBe(true);
expect(g.hold()).toBe(false);
g.hardDrop();
expect(g.hold()).toBe(true);
});
it('clears completed rows',()=>{
const g=new Game();
for(let x=0;x<10;x++)if(x<6)g.board[21][x]='J';
g.active={type:'I',cells:[[0,0],[1,0],[2,0],[3,0]],x:6,y:21,rotation:0,lastRotate:false};
g.lock();
expect(g.lines).toBe(1);
expect(g.score).toBeGreaterThanOrEqual(100);
});
it('pause freezes gravity',()=>{
const g=new Game();
const y=g.active.y;
g.paused=true;g.step(5000);
expect(g.active.y).toBe(y);
});
it('rotation preserves four cells',()=>{
const g=new Game();
g.spawn('T');
expect(g.rotate()).toBe(true);
expect(g.active.cells).toHaveLength(4);
});
});
