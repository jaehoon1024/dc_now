const fs=require('node:fs');const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/정재훈/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const snapshot=JSON.parse(fs.readFileSync(base+'/deploy/data.json','utf8'));
 const p=await browser.newPage({viewport:{width:1440,height:1100},acceptDownloads:true}),errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.route('**/*',async r=>{const u=new URL(r.request().url());if(u.hostname!=='development.test'){await r.abort();return;}const name=u.pathname==='/'?'index.html':u.pathname.slice(1),path=base+'/deploy/'+name;if(!['index.html','manage.html','manager-core.js','manager.js','manager.css','market.js','market.css','google-map.js','development.js','map-config.json','data.json'].includes(name)){await r.fulfill({status:404});return;}await r.fulfill({contentType:name.endsWith('.html')?'text/html':name.endsWith('.css')?'text/css':name.endsWith('.json')?'application/json':'application/javascript',body:fs.readFileSync(path)});});
 await p.goto('https://development.test/');await p.locator('#permitRows tr').first().waitFor();
 assert.match(await p.locator('#discoveryRibbon').innerText(),/138/);assert.match(await p.locator('#permitMetrics').innerText(),/49/);assert.match(await p.locator('#permitMetrics').innerText(),/47/);assert.match(await p.locator('#permitMetrics').innerText(),/42/);
 await p.locator('[data-permit-stage="공사 중"]').click();assert.match(await p.locator('#permitScope').innerText(),/^47건/);await p.locator('[data-permit-stage=""]').click();
 // One reset clears both market and permit conditions and returns defaults.
 await p.locator('[data-permit-stage="공사 중"]').click();
 await p.locator('#permitConnection').selectOption('ADDRESS_MATCH');
 await p.locator('#permitChart [data-permit-year]').first().press('Enter');
 await p.locator('[data-metric="count"]').click();await p.locator('#energyToggle').click();
 await p.locator('#reset').click();
 assert.equal(await p.locator('[data-permit-stage=""]').getAttribute('aria-pressed'),'true');
 assert.equal(await p.locator('#permitConnection').inputValue(),'');
 assert.match(await p.locator('#permitScope').innerText(),/^138건/);assert.doesNotMatch(await p.locator('#permitScope').innerText(),/허가 \d{4}년/);
 assert.match(await p.locator('#permitPageInfo').innerText(),/^1–10/);
 assert.equal(await p.locator('[data-metric="it"]').getAttribute('aria-pressed'),'true');assert.equal(await p.locator('#energyRows tr').count(),8);
 await p.locator('#permitNext').click();await p.locator('#reset').click();assert.match(await p.locator('#permitPageInfo').innerText(),/^1–10/);
 await p.locator('#permitConnection').selectOption('ADDRESS_MATCH');assert.match(await p.locator('#permitScope').innerText(),/^20건/);await p.locator('#permitConnection').selectOption('');
 await p.locator('#permitNext').click();assert.match(await p.locator('#permitPageInfo').innerText(),/^11–20/);await p.locator('#permitPrev').click();
 await p.locator('#search').fill('파주');assert.match(await p.locator('#permitScope').innerText(),/^1건/);await p.locator('#permitRows [data-permit-id]').first().click();assert.match(await p.locator('#permitBody').innerText(),/LG유플러스/);assert.match(await p.locator('#permitBody').innerText(),/RFS/);
 await p.locator('#permitNote').fill('공식 주소 대조 완료 · Phase 일정 확인 필요');await p.locator('#permitNoteForm button').click();assert.match(await p.locator('#permitNoteStatus').innerText(),/저장 완료/);await p.keyboard.press('Escape');await p.reload();await p.locator('#search').fill('파주');await p.locator('#permitRows [data-permit-id]').first().click();assert.match(await p.locator('#permitNote').inputValue(),/Phase 일정/);
 await p.locator('[data-master-site="LGU_PAJU"]').click();await p.locator('#detailDialog').waitFor({state:'visible'});assert.match(await p.locator('#detailBody').innerText(),/주소로 연결한 건축 인허가/);assert.match(await p.locator('#detailBody').innerText(),/200/);await p.locator('#closeDetail').click();
 await p.locator('#reset').click();await p.locator('#permitConnection').selectOption('AMBIGUOUS_ADDRESS');assert.match(await p.locator('#permitScope').innerText(),/^10건/);await p.locator('#permitRows [data-permit-id]').first().click();assert.ok(await p.locator('#permitBody [data-master-site]').count()>1);await p.keyboard.press('Escape');
 const dl=p.waitForEvent('download');await p.locator('#permitExport').click();assert.equal((await dl).suggestedFilename(),'dc-now-permits.csv');
 await p.locator('#permitConnection').selectOption('');await p.locator('#region').selectOption('경기도');assert.ok((await p.locator('#permitScope').innerText()).includes('지역·검색'));assert.equal(await p.locator('#energyRows tr').count(),1);assert.match(await p.locator('#energyRows').innerText(),/경기/);
 await p.locator('#reset').click();assert.equal(await p.locator('#energyRows tr').count(),8);await p.locator('#energyToggle').click();assert.equal(await p.locator('#energyRows tr').count(),16);
 const firstYear=await p.locator('#permitChart [data-permit-year]').first().getAttribute('data-permit-year');await p.locator('#permitChart [data-permit-year]').first().press('Enter');assert.match(await p.locator('#permitScope').innerText(),new RegExp('허가 '+firstYear+'년'));await p.locator('#permitChart [data-permit-year]').first().click();
 await p.setViewportSize({width:390,height:844});for(const id of ['permits','energyPanel']){await p.locator('#'+id).scrollIntoViewIfNeeded();assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth),390);}
 await p.locator('#permitRows [data-permit-id]').first().click();assert.equal(await p.locator('#permitDialog').evaluate(e=>e.getBoundingClientRect().width),390);await p.screenshot({path:base+'/output/design/development-mobile-detail.png'});await p.keyboard.press('Escape');assert.deepEqual(errors,[]);
 // A failed external refresh must leave rows available and show its actual collection status.
 const failed=JSON.parse(JSON.stringify(snapshot));failed.development_intelligence.collection.status='FAILED_KEPT_PREVIOUS';
 await p.route('https://development.test/data.json',r=>r.fulfill({json:failed}));await p.reload();await p.locator('#permitRows tr').first().waitFor();assert.match(await p.locator('#discoveryRibbon').innerText(),/이전 자료 유지/);assert.match(await p.locator('#runs').innerText(),/실패/);assert.equal(await p.locator('#permitRows tr').count(),10);
 console.log('PASS: live permit facts, stage/connection filters, pagination, source detail, persistent review note, master link, ambiguous campuses, CSV, region energy, timeline keyboard, mobile and failed-refresh preservation.');await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
