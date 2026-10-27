const CACHE='orchestrator-shell-__BUILD__';
const PRECACHE=/*__PRECACHE__*/[];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/','/manifest.webmanifest','/icon-192.png','/icon-512.png',...PRECACHE])).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==location.origin||u.pathname.startsWith('/api/'))return;e.respondWith(fetch(e.request).then(r=>{if(r.ok&&(e.request.mode==='navigate'||u.pathname.startsWith('/assets/'))) {const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request.mode==='navigate'?'/':e.request,copy));}return r;}).catch(()=>caches.match(e.request).then(r=>r||(e.request.mode==='navigate'?caches.match('/'):Response.error()))));});
