const fs=require('node:fs');
const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/정재훈/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];
(async()=>{
 const api=require(base+'/dashboard/google-map.js');
 const point={site_code:'A',latitude:37.5,longitude:127,coordinate_quality:'A'};
 assert.equal(api.valid({...point,latitude:null}),false);
 assert.equal(api.valid({...point,longitude:0}),false);
 assert.equal(api.precise({...point,coordinate_quality:'C'}),false);
 assert.equal(api.groups([point,{...point,site_code:'B'}, {...point,site_code:'C',coordinate_quality:'C'}],7).flat().length,2);
 assert.equal(api.groups([point,{...point,site_code:'B',coordinate_quality:'C'}],7,true).flat().length,2);
 assert.equal(api.total({operating_it_load_mw:null,development_it_load_mw:null},'it'),null);
 assert.equal(api.total({operating_it_load_mw:20,development_it_load_mw:30},'it'),50);
 const b=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const data=JSON.parse(fs.readFileSync(base+'/deploy/data.json','utf8'));
 const p=await b.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.route('**/*',async r=>{
  const u=new URL(r.request().url());if(u.hostname!=='market.test'){await r.abort();return;}
  const file=u.pathname==='/'?'index.html':u.pathname.slice(1),path=base+'/deploy/'+file;
  if(!['index.html','manage.html','data.json','map-config.json','manager.js','manager.css','manager-core.js','market.js','market.css','google-map.js','development.js'].includes(file)){await r.fulfill({status:404});return;}
  await r.fulfill({contentType:file.endsWith('.html')?'text/html':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'application/javascript',body:fs.readFileSync(path)});
 });
 await p.goto('https://market.test/');await p.locator('#siteRows tr').first().waitFor();
 assert.match(await p.locator('#scopeNote').innerText(),/66곳/);
 assert.equal(await p.locator('#initialMarket').isVisible(),false);
 await p.locator('[name=basis][value=verified]').check();assert.match(await p.locator('#kpis').innerText(),/146\.3/);assert.equal(await p.locator('#supplyChart .capacity-bar').count(),0);assert.match(await p.locator('#supplyChart').innerText(),/용량 미확인/);
 await p.locator('[name=basis][value=planning]').check();await p.locator('[data-stage="DEVELOPMENT"]').click();assert.match(await p.locator('#scopeNote').innerText(),/13곳/);
 await p.locator('#reset').click();await p.locator('[data-year="2027"]').press('Enter');assert.match(await p.locator('#scopeNote').innerText(),/RFS 2027년/);assert.equal(await p.locator('#siteRows tr').count(),3);await p.locator('[data-year="2027"]').click();assert.match(await p.locator('#scopeNote').innerText(),/66곳/);
 await p.locator('#search').fill('파주');await p.locator('[data-detail="LGU_PAJU"]').first().click();assert.match(await p.locator('#detailBody').innerText(),/40 MW/);assert.match(await p.locator('#detailBody').innerText(),/133\.3/);assert.match(await p.locator('#detailBody').innerText(),/2027-06/);assert.match(await p.locator('#editorLink').getAttribute('href'),/manage.html#detail\/LGU_PAJU\/planning$/);await p.keyboard.press('Escape');
 await p.locator('#reset').click();await p.locator('#next').click();assert.match(await p.locator('#pageInfo').innerText(),/11–20/);await p.locator('[data-sort="it"]').click();assert.match(await p.locator('#siteRows tr').first().innerText(),/파주/);
 const download=p.waitForEvent('download');await p.locator('#download').click();assert.equal((await download).suggestedFilename(),'dc-now-market.csv');
 await p.locator('#scope').selectOption('ALL');assert.match(await p.locator('#scopeNote').innerText(),/146곳/);
 await p.locator('#reset').click();await p.locator('#region').selectOption('경기도');assert.match(await p.locator('#scopeNote').innerText(),/23곳/);
 await p.locator('#reset').click();await p.setViewportSize({width:390,height:844});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth),390);await p.locator('#search').fill('파주');await p.locator('[data-detail="LGU_PAJU"]').first().click();assert.equal(await p.locator('#detailDialog').evaluate(e=>e.getBoundingClientRect().width),390);await p.keyboard.press('Escape');
 await p.goto('https://market.test/#detail/KT_GASAN');await p.waitForURL('**/manage.html#detail/KT_GASAN');await p.getByRole('heading',{name:'kt cloud 가산 AI 데이터센터',exact:true}).waitFor();
 await p.goto('https://market.test/manage.html#detail/KT_GASAN/planning');await p.locator('#planValue').waitFor();assert.equal(await p.locator('#planValue').inputValue(),'26');
 await p.locator('#planValue').fill('52');await p.locator('#planMethod').fill('새 대시보드 연동 테스트');await p.locator('#planningForm button[type=submit]').click();await p.locator('#feedback').filter({hasText:'수정안 저장 완료'}).waitFor();
 await p.goto('https://market.test/');await p.locator('#search').fill('kt cloud 가산');assert.match(await p.locator('#siteRows').innerText(),/52/);assert.match(await p.locator('#siteRows').innerText(),/수정안/);
 await p.evaluate(()=>{localStorage.removeItem('dc-now-planning-drafts-v1');window.dispatchEvent(new StorageEvent('storage',{key:'dc-now-planning-drafts-v1'}));});assert.match(await p.locator('#siteRows').innerText(),/26/);
 await p.locator('#reset').click();await p.setViewportSize({width:1440,height:1100});await p.screenshot({path:base+'/output/design/market-production-desktop.png'});await p.screenshot({path:base+'/output/design/market-production-full.png',fullPage:true});
 await p.locator('#search').fill('파주');await p.locator('[data-detail="LGU_PAJU"]').first().click();await p.screenshot({path:base+'/output/design/market-production-detail.png'});
 assert.deepEqual(errors,[]);
 // Google API is mocked here; no billing or credentials are needed for marker interaction checks.
 const mapPage=await b.newPage({viewport:{width:1000,height:800}});
 await mapPage.addInitScript(()=>{
  window.google={maps:{importLibrary:async name=>name==='maps'?{Map:class{constructor(e){this.zoom=7;this.e=e;}addListener(){}getZoom(){return this.zoom;}setZoom(n){this.zoom=n;}panTo(){}setCenter(){}fitBounds(){}}}:{AdvancedMarkerElement:class{constructor(o){Object.assign(this,o);this._map=o.map;this.content=o.content;window.__mapElement.append(this.content);}set map(v){this._map=v;if(!v)this.content.remove();}get map(){return this._map;}}}}};
 });
 await mapPage.route('https://market.test/',r=>r.fulfill({contentType:'text/html',body:'<div id="googleMap"></div><div id="mapStatus"></div><div id="map"></div>'}));await mapPage.goto('https://market.test/');await mapPage.addScriptTag({content:fs.readFileSync(base+'/dashboard/google-map.js','utf8')});
 await mapPage.route('https://market.test/map-config.json',r=>r.fulfill({json:{browser_key:'test-only',map_id:'test-only'}}));
 await mapPage.evaluate(async()=>{window.__mapElement=document.querySelector('#map');window.selectedCodes=[];window.testMap=new DCGoogleMap(window.__mapElement,{onSelect:c=>selectedCodes.push(c)});await testMap.init('https://market.test/map-config.json');testMap.update([{site_code:'X',site_name:'Test operating',latitude:37.5,longitude:127,coordinate_quality:'A',lifecycle_group:'OPERATING'},{site_code:'Y',site_name:'Test unknown',latitude:35,longitude:129,coordinate_quality:'C',lifecycle_group:'UNKNOWN'}],{approximate:false});});
 assert.equal(await mapPage.locator('.dc-map-marker').count(),1);await mapPage.locator('.dc-map-marker').click();assert.deepEqual(await mapPage.evaluate(()=>selectedCodes),['X']);
 await mapPage.evaluate(()=>testMap.update(testMap.rows,{approximate:true}));assert.equal(await mapPage.locator('.dc-map-marker').count(),2);assert.equal(await mapPage.locator('.dc-map-marker.approximate.unknown').count(),1);
 console.log('PASS: market filters, forecast, drawer, CSV, mobile, legacy links, key-in and draft synchronization; Google marker eligibility, clustering and selection (mock Google API).');await b.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
