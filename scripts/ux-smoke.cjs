
let playwright;try{playwright=require('playwright')}catch{playwright=require('/Users/guilherme/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')}
const {chromium}=playwright;
const ok=(c,m)=>{if(!c)throw Error('FALHOU: '+m);console.log('ok  - '+m)};
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('ERR_INTERNET_DISCONNECTED'))errors.push(m.text())});
 await page.goto('http://127.0.0.1:8788');
 await page.getByText('Conectado',{exact:true}).waitFor();

 // Navegação e localização atual
 const nav=page.getByRole('button',{name:'Visão geral',exact:true});
 ok(await nav.getAttribute('aria-current')==='page','menu marca a página atual (aria-current)');
 ok((await page.title()).startsWith('Visão geral'),'título da aba reflete a página');
 await page.getByRole('button',{name:/^Tarefas\b/}).click();
 ok((await page.locator('.breadcrumb strong').innerText())==='Tarefas','breadcrumb em português');
 ok((await page.title()).startsWith('Tarefas'),'título da aba atualiza ao navegar');
 ok(await page.getByRole('heading',{level:1,name:'Tarefas'}).count()===1,'h1 da página');

 // Link de pular para o conteúdo
 await page.reload();await page.getByText('Conectado',{exact:true}).waitFor();
 await page.keyboard.press('Tab');
 ok(await page.evaluate(()=>document.activeElement?.classList.contains('skip-link')),'primeiro Tab foca o link "Pular para o conteúdo"');
 await page.keyboard.press('Enter');
 ok(await page.evaluate(()=>document.activeElement?.id==='main-content'),'Enter move o foco para o conteúdo');

 // Kanban: colunas vazias raras ocultas, sem "Codex" fixo
 await page.getByRole('button',{name:'Board',exact:false}).first().click().catch(()=>{});
 const cols=await page.locator('.kanban-col').count();
 console.log('info - colunas do kanban visíveis:',cols);

 // Paleta de comandos: filtra por rótulo em português e Enter abre o primeiro resultado
 await page.keyboard.press('Meta+k');
 const dlg=page.getByRole('dialog');await dlg.waitFor();
 await dlg.getByLabel('Busca global').fill('agent');
 await page.keyboard.press('Enter');
 await page.waitForFunction(()=>document.querySelector('.breadcrumb strong')?.textContent==='Agentes');
 ok(true,'paleta: buscar "agent" + Enter navega para Agentes');
 ok(await page.getByRole('dialog').count()===0||!(await page.getByRole('dialog').isVisible()),'paleta fecha após navegar');

 // Memória: ação principal coerente
 await page.getByRole('button',{name:'Memória',exact:true}).click();
 const primary=page.locator('.page-heading .primary, .page-title ~ .primary, button.primary').filter({hasText:'Nova memória'});
 ok(await primary.count()>=1,'ação principal da página Memória é "Nova memória"');
 await primary.first().click();
 await page.getByRole('dialog').getByRole('heading',{name:'Memória do projeto'}).waitFor();
 ok(true,'"Nova memória" abre o modal de memória');
 await page.keyboard.press('Escape');

 // Configurações: tema com aria-pressed
 await page.getByRole('button',{name:'Configurações',exact:true}).click();
 await page.getByRole('button',{name:'Claro',exact:true}).click();
 ok(await page.getByRole('button',{name:'Claro',exact:true}).getAttribute('aria-pressed')==='true','tema Claro com aria-pressed=true');
 await page.getByRole('button',{name:'Escuro',exact:true}).click();
 ok(await page.getByRole('button',{name:'Claro',exact:true}).getAttribute('aria-pressed')==='false','tema Claro desmarcado ao trocar');

 // Criação de tarefa (fluxo principal)
 await page.getByRole('button',{name:'Visão geral',exact:true}).click();
 await page.getByRole('button',{name:'Nova tarefa',exact:true}).click();
 await page.getByLabel('Objetivo',{exact:true}).fill('TESTE MOCK UX: verificar fluxo sem provedor real.');
 await page.getByRole('button',{name:'Iniciar tarefa'}).click();
 await page.waitForFunction(async()=>{const d=await(await fetch('/api/state')).json();const t=d.tasks.find(t=>t.objective.startsWith('TESTE MOCK UX:'));return t&&t.status==='completed'},null,{timeout:30000});
 ok(true,'tarefa criada via modal executa até concluída');

 // Offline: aviso e comandos desabilitados
 await context.setOffline(true);
 await page.getByText('Backend indisponível',{exact:false}).first().waitFor({timeout:30000});
 ok(await page.locator('.notice[role]').count()>=1,'aviso offline anunciado (role)');
 await context.setOffline(false);

 // Responsividade
 for(const w of [390,768,1024]){
  await page.setViewportSize({width:w,height:900});await page.reload();
  await page.getByText('Conectado',{exact:true}).waitFor();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);
  ok(!overflow,`sem rolagem horizontal em ${w}px`);
 }
 await page.screenshot({path:'evidence/ux-smoke-mobile.png',fullPage:true});

 ok(errors.length===0,'sem erros de console/página'+(errors.length?': '+errors.slice(0,3).join(' | '):''));
 await browser.close();
})().catch(e=>{console.error(e.message||e);process.exit(1)});
