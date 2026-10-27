const fs=require('fs'),path=require('path'),crypto=require('crypto');
const dist=path.resolve(__dirname,'../frontend/dist');
const assets=fs.readdirSync(path.join(dist,'assets')).map(f=>'/assets/'+f);
const sw=fs.readFileSync(path.join(dist,'sw.js'),'utf8');
const version=crypto.createHash('sha256').update(sw+assets.join(',')).digest('hex').slice(0,12);
fs.writeFileSync(path.join(dist,'sw.js'),sw.replace('__BUILD__',version).replace('/*__PRECACHE__*/[]',JSON.stringify(assets)));
console.log('PWA precache: '+assets.length+' versioned assets');
