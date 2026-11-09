import React, {useEffect, useRef, useState} from 'react';
import {ChevronLeft, ChevronRight} from 'lucide-react';

export function Paginated({total, resetKey, label, children}:{total:number;resetKey:string;label:string;children:(start:number,end:number)=>React.ReactNode}) {
 const [page,setPage]=useState(1),[size,setSize]=useState(10);
 const body=useRef<HTMLDivElement>(null);
 const pages=Math.max(1,Math.ceil(total/size)),current=Math.min(page,pages),start=(current-1)*size;
 useEffect(()=>setPage(1),[resetKey,size]);
 useEffect(()=>{setPage(p=>Math.min(p,pages))},[pages]);
 useEffect(()=>{body.current?.scrollTo({top:0})},[current,resetKey,size]);
 return <div className="paginated"><div className="collection-scroll" ref={body} tabIndex={0} role="region" aria-label={label}>{children(start,start+size)}</div><nav className="pagination" aria-label={'Paginação de '+label}><span role="status">{total?`${start+1}–${Math.min(start+size,total)} de ${total}`:'Nenhum resultado'}</span><label>Por página <select aria-label={'Itens por página de '+label} value={size} onChange={e=>setSize(Number(e.target.value))}>{[10,25,50].map(n=><option key={n}>{n}</option>)}</select></label><div><button type="button" className="secondary" aria-label={'Página anterior de '+label} disabled={current===1} onClick={()=>setPage(current-1)}><ChevronLeft size={15}/></button><span>{current} / {pages}</span><button type="button" className="secondary" aria-label={'Próxima página de '+label} disabled={current===pages} onClick={()=>setPage(current+1)}><ChevronRight size={15}/></button></div></nav></div>;
}
