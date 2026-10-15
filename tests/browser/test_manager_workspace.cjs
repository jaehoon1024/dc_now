const fs=require('node:fs');
const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/정재훈/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];
if(!base)throw Error('Pass workspace path');
(async()=>{
 const chrome=['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(x=>fs.existsSync(x));
 const browser=await chromium.launch({headless:true,executablePath:chrome});
 const data=JSON.parse(fs.readFileSync(base+'/deploy/data.json','utf8'));
 const publicCount=data.sites.filter(x=>x.commercial_scope_status==='IN_SCOPE'&&x.commercial_review_status==='CONFIRMED').length;
 async function setup(internal=false){
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let approved=false,decisions=[],planningWrites=[],publishRequests=0;
  const workspace=JSON.parse(JSON.stringify(data));
  const sample={id:'TEST-REVIEW',label:'IT_LOAD_MW',review_status:'CANDIDATE',created_at:'2026-10-13',scope_type:'PROJECT',raw_value:'20',raw_unit:'MW',normalized_value_mw:20,document_url:'https://example.com/public',can_publish:false};
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url());
   if(u.hostname!=='workspace.test'){await route.abort();return;}
   const p=u.pathname;
   if(p==='/'){let html=fs.readFileSync(base+'/dashboard/manager.html','utf8');if(internal)html=html.replace('data-mode="public"','data-mode="internal"');await route.fulfill({contentType:'text/html',body:html});}
   else if(['/manager.css','/manager.js','/manager-core.js'].includes(p))await route.fulfill({contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.readFileSync(base+'/dashboard'+p,'utf8')});
   else if(p==='/data.json'||p==='/internal/v1/workspace')await route.fulfill({json:workspace});
   else if(p==='/internal/v1/planning-values'){
    const d=route.request().postDataJSON();planningWrites.push(d);const key=x=>[x.site_code,x.scope_type,x.scope_code,x.field_name,x.bucket].join('|');
    workspace.planning_values=(workspace.planning_values||[]).filter(v=>key(v)!==key(d)).concat({...d,version:d.expected_version+1});
    await route.fulfill({json:{version:d.expected_version+1}});
   }
   else if(p==='/internal/v1/planning-import'){
    const d=route.request().postDataJSON();for(const item of d.items){planningWrites.push(item);const key=x=>[x.site_code,x.scope_type,x.scope_code,x.field_name,x.bucket].join('|');workspace.planning_values=workspace.planning_values.filter(v=>key(v)!==key(item)).concat({...item,version:item.expected_version+1});}
    await route.fulfill({json:{saved:d.items.length}});
   }
   else if(p==='/internal/v1/publish'){publishRequests++;await route.fulfill({status:202,json:{status:'queued'}});}
   else if(p==='/internal/v1/review-queue')await route.fulfill({json:{capacity:approved?[]:[sample]}});
   else if(p==='/internal/v1/quality')await route.fulfill({json:{review_queue:{capacity:approved?0:1},checks:{}}});
   else if(p==='/internal/v1/review-history')await route.fulfill({json:{items:approved?[{actor_id:'browser-test',action:'REVIEW_APPROVE',entity_type:'CAPACITY',reason:'checked',occurred_at:'2026-10-13'}]:[]}});
   else if(p==='/internal/v1/review'){const body=route.request().postDataJSON();decisions.push(body);approved=true;await route.fulfill({json:{review_status:'CONFIRMED'}});}
   else await route.fulfill({status:404,body:'not found'});
  });
  await page.goto('https://workspace.test/');if(!internal)await page.locator('#snapshotAt').filter({hasText:/\d{4}/}).waitFor();return{page,errors,decisions,planningWrites,publishCount:()=>publishRequests};
 }
 const {page,errors}=await setup();
 await page.locator('#content h1').filter({hasText:'오늘의 업무'}).waitFor();
 await page.getByRole('button',{name:'센터 현황',exact:true}).first().click();
 await page.waitForFunction(()=>location.hash==='#register');
 assert.equal(await page.locator('tbody tr').count(),publicCount);
 await page.locator('[data-filter="scope"]').selectOption('ENTERPRISE');
 assert.equal(await page.locator('tbody tr').count(),data.sites.filter(x=>x.facility_scope==='ENTERPRISE').length);
 await page.locator('#resetFilters').click();
 await page.locator('#siteSearch').fill('zzzz-no-such-center');
 assert.equal(await page.locator('tbody tr').count(),0);
 await page.locator('#resetFilters').click();
 await page.locator('[data-compare]').nth(0).check();await page.locator('[data-compare]').nth(1).check();await page.locator('#compareOpen').click();
 assert.equal(await page.locator('#compareDialog').evaluate(d=>d.open),true);
 await page.locator('#compareDialog .close').click();
 await page.locator('tbody [data-site]').first().click();
 await page.locator('[data-detail-tab="phases"]').waitFor();
 await page.locator('[data-detail-tab="phases"]').click();
 assert.ok((await page.locator('#content').innerText()).includes('Phase'));
 await page.locator('[data-detail-tab="sources"]').click();
 await page.locator('[data-page="supply"]').click();
 await page.locator('[data-supply-metric="grid"]').click();
 await page.locator('[data-page="map"]').click();
 assert.ok((await page.locator('iframe').getAttribute('src')).startsWith('https://maps.google.com/maps?'));
 await page.locator('[data-page="review"]').click();await page.waitForFunction(()=>document.querySelector('#content').innerText.includes('인증'));assert.ok((await page.locator('#content').innerText()).includes('인증'));
 for(const p of ['companies','sources','ops','projects','home']){await page.locator('[data-page="'+p+'"]').click();await page.waitForFunction(p=>location.hash==='#'+p,p);}
 await page.locator('[data-page="sources"]').click();
 await page.locator('#sourceStatus').selectOption('API_NOT_CONNECTED');
 const apiSources=data.source_assessment.sources.filter(x=>x.connection_status==='API_NOT_CONNECTED');
 assert.equal(await page.locator('[data-source-code]').count(),apiSources.length);
 const hub=page.locator('[data-source-code="BUILDING_HUB_PERMIT"]');assert.match(await hub.innerText(),/138건/);assert.match(await hub.innerText(),/API 수집기 미연결/);
 await hub.locator('summary').click();assert.match(await hub.locator('details').innerText(),/제3자|경유/);
 await page.locator('#sourceStatus').selectOption('');
 await page.locator('#sourceGroup').selectOption('유료 전문 데이터');
 assert.equal(await page.locator('.panel').filter({has:page.getByRole('heading',{name:'소스별 실제 기여도',exact:true})}).locator('tbody tr').count(),3);
 assert.ok((await page.locator('#content').innerText()).includes('계약 필요 · 미취득'));
 await page.locator('#sourceGroup').selectOption('');
 assert.equal(await page.locator('.panel').filter({has:page.getByRole('heading',{name:'소스별 실제 기여도',exact:true})}).locator('tbody tr').count(),data.source_assessment.sources.length);
 await page.screenshot({path:base+'/output/design/source-quality-desktop.png',fullPage:true});
 await page.evaluate(()=>location.hash='#detail/STT_SEOUL1');
 await page.locator('[data-detail-tab="facility"]').waitFor();
 await page.locator('[data-detail-tab="facility"]').click();
 assert.ok((await page.locator('#content').innerText()).includes('설계 PUE 상한 미만'));
 assert.ok((await page.locator('#content').innerText()).includes('2026-06'));
 await page.evaluate(()=>location.hash='#detail/LGU_PAJU');
 await page.getByRole('heading',{name:'LG유플러스 파주 AI 데이터센터',exact:true}).waitFor();
 await page.locator('[data-detail-tab="phases"]').click();
 assert.ok((await page.locator('#content').innerText()).includes('2027-06'));
 assert.ok((await page.locator('#content').innerText()).includes('준공 예정'));
 await page.locator('[data-detail-tab="capacity"]').click();
 assert.ok((await page.locator('#content').innerText()).includes('200 MW'));
 await page.screenshot({path:base+'/output/design/paju-development.png',fullPage:true});
 await page.evaluate(()=>location.hash='#detail/KT_GASAN');
 await page.getByRole('heading',{name:'kt cloud 가산 AI 데이터센터',exact:true}).waitFor();
 await page.locator('[data-detail-tab="capacity"]').click();
 assert.ok((await page.locator('#content').innerText()).includes('26 MW'));
 assert.ok((await page.locator('#content').innerText()).includes('40 MW'));
 for(const [code,name,period] of [['SGC_GUNSAN','SGC·kt cloud 군산 AI 데이터센터','2028-Q1'],['SK_AWS_ULSAN','SK-AWS 울산 AI 데이터센터','2027'],['SKHORIZON_GURO','SK 구로 AI 데이터센터','2030']]){
  await page.evaluate(code=>location.hash='#detail/'+code,code);
  await page.getByRole('heading',{name,exact:true}).waitFor();
  await page.locator('[data-detail-tab="phases"]').click();
  assert.ok((await page.locator('#content').innerText()).includes(period),code+' forecast precision');
 }
 await page.screenshot({path:base+'/output/design/kt-sk-development.png',fullPage:true});
 await page.evaluate(()=>location.hash='#detail/KT_GASAN');
 await page.getByRole('heading',{name:'kt cloud 가산 AI 데이터센터',exact:true}).waitFor();
 await page.locator('[data-detail-tab="planning"]').click();
 await page.locator('#planValue').fill('52');await page.locator('#planMethod').fill('브라우저 수정안 테스트');
 await page.locator('#planningForm button[type="submit"]').click();
 await page.locator('#feedback').filter({hasText:'내 브라우저 수정안 저장 완료'}).waitFor();
 assert.ok((await page.locator('.metrics').innerText()).includes('52 MW'));
 await page.locator('#valueMode').selectOption('verified');assert.ok((await page.locator('.metrics').innerText()).includes('26 MW'));
 await page.locator('#valueMode').selectOption('planning');assert.ok((await page.locator('.metrics').innerText()).includes('52 MW'));
 await page.reload();await page.locator('[data-detail-tab="planning"]').waitFor();assert.ok((await page.locator('.metrics').innerText()).includes('52 MW'));
 await page.locator('[data-detail-tab="planning"]').click();
 const download=page.waitForEvent('download');await page.locator('#exportDrafts').click();const file=await download;assert.equal(file.suggestedFilename(),'dc-now-planning-drafts.json');
 await page.locator('#clearDrafts').click();assert.ok((await page.locator('.metrics').innerText()).includes('26 MW'));
 await page.screenshot({path:base+'/output/design/planning-keyin-desktop.png',fullPage:true});
 await page.locator('[data-page="home"]').click();
 await page.screenshot({path:base+'/output/design/manager-live-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:900});
 for(const p of ['home','register','detail','planning','supply','map','review','sources','ops']){
  if(p==='detail'){await page.locator('[data-page="register"]').click();await page.locator('tbody [data-site]').first().click();}else if(p==='planning')await page.locator('[data-detail-tab="planning"]').click();else await page.locator('[data-page="'+p+'"]').click();
  await page.waitForTimeout(50);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false,'mobile overflow '+p);
 }
 assert.deepEqual(errors,[]);
 const admin=await setup(true);await admin.page.locator('#token').fill('test-only-token');await admin.page.locator('#reviewer').fill('browser-test');await admin.page.locator('#connectForm button').click();
 await admin.page.locator('#content h1').filter({hasText:'오늘의 업무'}).waitFor();
 assert.equal(await admin.page.locator('#token').inputValue(),'');
 await admin.page.locator('[data-page="review"]').click();await admin.page.locator('#note').fill('Official source reviewed in browser test');await admin.page.locator('#reviewForm button[type="submit"]').click();
 await admin.page.locator('#feedback').filter({hasText:'승인 완료'}).waitFor();
 assert.equal(admin.decisions.length,1);assert.equal(admin.decisions[0].expected_status,'CANDIDATE');assert.equal(admin.decisions[0].decision,'approve');
 assert.deepEqual(admin.errors,[]);
 await admin.page.evaluate(()=>location.hash='#detail/KT_GASAN');await admin.page.locator('[data-detail-tab="planning"]').waitFor();await admin.page.locator('[data-detail-tab="planning"]').click();
 await admin.page.locator('#planValue').fill('31');await admin.page.locator('#planMethod').fill('담당자 원장 수정 테스트');await admin.page.locator('#planningForm button[type="submit"]').click();
 await admin.page.locator('#feedback').filter({hasText:'원장 저장 완료'}).waitFor();assert.equal(admin.planningWrites[0].expected_version,0);assert.equal(admin.planningWrites[0].value,31);assert.ok((await admin.page.locator('.metrics').innerText()).includes('31 MW'));
 const imported={...admin.planningWrites[0],value:37,expected_version:1};await admin.page.locator('#importPlanning').setInputFiles({name:'correction.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'dc-now-planning-v1',items:[imported]}))});
 await admin.page.locator('#feedback').filter({hasText:'1개 수정안을 원장에 저장'}).waitFor();assert.ok((await admin.page.locator('.metrics').innerText()).includes('37 MW'));
 await admin.page.locator('#publishPlanning').click();await admin.page.locator('#feedback').filter({hasText:'게시를 요청'}).waitFor();assert.equal(admin.publishCount(),1);
 assert.deepEqual(admin.errors,[]);
 console.log('PASS: real public data, scope/search/reset, comparison, project/source detail, supply metric, Google address map, private review separation, all menus, 390px layout, authenticated review and audit refresh (mock write only)');
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1);});
