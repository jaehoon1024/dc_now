(function(root){
  'use strict';
  const valid=s=>Number.isFinite(Number(s.latitude))&&Number.isFinite(Number(s.longitude))&&s.latitude!=null&&s.longitude!=null&&Number(s.latitude)>=32&&Number(s.latitude)<=40&&Number(s.longitude)>=124&&Number(s.longitude)<=132;
  const precise=s=>valid(s)&&['A','B'].includes(s.coordinate_quality);
  function projected(s,zoom){const lat=Number(s.latitude)*Math.PI/180,scale=256*2**zoom;return {x:(Number(s.longitude)+180)/360*scale,y:(1-Math.log(Math.tan(lat)+1/Math.cos(lat))/Math.PI)/2*scale};}
  function groups(rows,zoom,approximate=false){
    const cells=new Map();
    rows.filter(s=>approximate?valid(s):precise(s)).forEach(s=>{const p=projected(s,zoom),key=Math.floor(p.x/42)+':'+Math.floor(p.y/42);if(!cells.has(key))cells.set(key,[]);cells.get(key).push(s);});
    return [...cells.values()];
  }
  function total(s,metric){const suffix=metric==='grid'?'grid_intake_mw':'it_load_mw';const nums=[s['operating_'+suffix],s['development_'+suffix]].filter(x=>x!=null&&Number.isFinite(Number(x)));return nums.length?nums.reduce((a,b)=>a+Number(b),0):null;}
  class DCGoogleMap{
    constructor(element,{onSelect=()=>{},onStatus=()=>{},onReady=()=>{}}={}){this.element=element;this.onSelect=onSelect;this.onStatus=onStatus;this.onReady=onReady;this.ready=false;this.markers=[];this.rows=[];this.options={metric:'it',approximate:false};}
    async init(url){
      try{
        const response=await fetch(url,{cache:'no-store'});if(!response.ok)return false;
        const config=await response.json();
        if(!config.browser_key){this.onStatus('Google 주소 조회 · 센터를 선택하면 해당 주소로 이동합니다.');return false;}
        await this.load(config.browser_key);
        const [{Map:GoogleMap},{AdvancedMarkerElement}]=await Promise.all([google.maps.importLibrary('maps'),google.maps.importLibrary('marker')]);
        this.AdvancedMarkerElement=AdvancedMarkerElement;
        this.map=new GoogleMap(this.element,{center:{lat:36.3,lng:127.8},zoom:7,mapId:config.map_id||'DEMO_MAP_ID',mapTypeControl:false,streetViewControl:false,fullscreenControl:true,gestureHandling:'cooperative'});
        this.ready=true;this.map.addListener('idle',()=>this.paint());this.onReady();return true;
      }catch{this.onStatus('전국 위치 지도에 연결하지 못했습니다. 주소 지도와 센터 원장을 이용할 수 있습니다.');this.ready=false;return false;}
    }
    load(key){
      if(root.google?.maps?.importLibrary)return Promise.resolve();
      return new Promise((resolve,reject)=>{
        const script=document.createElement('script'),callback='dcNowGoogleLoaded';let done=false;
        const finish=error=>{if(done)return;done=true;clearTimeout(timer);delete root[callback];error?reject(new Error('map_unavailable')):resolve();};
        const timer=setTimeout(()=>{script.remove();finish(true);},15000);
        root[callback]=()=>finish(false);root.gm_authFailure=()=>{this.ready=false;this.markers.forEach(m=>m.map=null);this.onStatus('Google 위치 지도 인증을 확인해야 합니다. 주소 지도는 계속 이용할 수 있습니다.');this.element.hidden=true;const fallback=document.querySelector('#googleMap');if(fallback)fallback.hidden=false;finish(true);};
        script.src='https://maps.googleapis.com/maps/api/js?'+new URLSearchParams({key,loading:'async',callback,libraries:'maps,marker',v:'quarterly',language:'ko',region:'KR',auth_referrer_policy:'origin'});script.async=true;script.onerror=()=>finish(true);document.head.append(script);
      });
    }
    update(rows,options){this.rows=rows;this.options={...this.options,...options};if(this.ready)this.paint();}
    paint(){
      if(!this.ready)return;this.markers.forEach(m=>m.map=null);this.markers=[];
      const selected=this.rows.filter(s=>this.options.approximate?valid(s):precise(s));
      const clusters=groups(this.rows,this.map.getZoom(),this.options.approximate);
      for(const sites of clusters){
        const position={lat:sites.reduce((n,s)=>n+Number(s.latitude),0)/sites.length,lng:sites.reduce((n,s)=>n+Number(s.longitude),0)/sites.length};
        const content=document.createElement('button');content.type='button';content.className='dc-map-marker';
        const stages=new Set(sites.map(s=>s.lifecycle_group));content.classList.add(stages.size===1&&stages.has('OPERATING')?'operating':stages.size===1&&stages.has('DEVELOPMENT')?'developing':stages.has('MIXED')||stages.size>1?'mixed':'unknown');
        if(sites.some(s=>!precise(s)))content.classList.add('approximate');
        const values=sites.map(s=>total(s,this.options.metric)).filter(x=>x!==null),amount=values.length?values.reduce((a,b)=>a+b,0):null;
        const size=sites.length>1?Math.min(45,27+Math.log2(sites.length)*3):this.options.metric==='count'||amount===null?23:Math.min(42,18+Math.sqrt(amount)*1.5);
        content.style.width=content.style.height=size+'px';content.textContent=sites.length>1?String(sites.length):'';
        content.title=sites.length>1?`${sites.length}개 센터 · 눌러서 확대`:sites[0].site_name+(precise(sites[0])?' · 검증 좌표':' · 근사 좌표');content.setAttribute('aria-label',content.title);
        const marker=new this.AdvancedMarkerElement({map:this.map,position,content,title:content.title});
        content.addEventListener('click',()=>{if(sites.length===1)this.onSelect(sites[0].site_code);else if(this.map.getZoom()<16){const bounds=new google.maps.LatLngBounds();sites.forEach(s=>bounds.extend({lat:Number(s.latitude),lng:Number(s.longitude)}));this.map.fitBounds(bounds);this.map.setZoom(Math.min(16,this.map.getZoom()+2));}else this.showGroup(sites);});
        this.markers.push(marker);
      }
      this.onStatus(`지도 ${selected.length}/${this.rows.length}곳 · ${clusters.length}개 표시 · ${this.options.approximate?'근사 좌표 포함':'A/B 검증 좌표'} · 미표시 대상은 원장에서 조회`);
    }
    showGroup(sites){
      const content=document.createElement('div');content.className='dc-map-group';
      for(const s of sites){const button=document.createElement('button');button.textContent=s.site_name;button.addEventListener('click',()=>{this.info?.close();this.onSelect(s.site_code);});content.append(button);}
      this.info?.close();this.info=new google.maps.InfoWindow({content,position:{lat:Number(sites[0].latitude),lng:Number(sites[0].longitude)}});this.info.open({map:this.map});
    }
    select(s){if(!this.ready||!valid(s)||!precise(s)&&!this.options.approximate)return false;this.map.panTo({lat:Number(s.latitude),lng:Number(s.longitude)});this.map.setZoom(14);return true;}
    fit(){if(!this.ready)return;this.map.setCenter({lat:36.3,lng:127.8});this.map.setZoom(7);}
  }
  root.DCGoogleMap=DCGoogleMap;
  if(typeof module!=='undefined')module.exports={valid,precise,groups,total};
})(typeof window==='undefined'?globalThis:window);
