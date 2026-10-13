#!/usr/bin/env python3
"""Fill working estimates once; never overwrite an editor or verified value."""
import argparse,json,statistics
from datetime import date
from sqlalchemy import create_engine,text
from src04_rss_collector import load_env_file,resolve_database_url
from public_api import PublicRepository
from src21_build_static_site import build_payload
from planning_values import write_value
PUE=1.5
REVIEW_DATE='2026-10-13'

def proposals(data):
    centers=[s for s in data['sites'] if s.get('commercial_scope_status')=='IN_SCOPE' and s.get('commercial_review_status')=='CONFIRMED']
    sample=[float(s['operating_it_load_mw']) for s in centers if s.get('operating_it_load_mw') is not None and float(s['operating_it_load_mw'])>0]
    median=statistics.median(sample) if sample else None
    out=[]
    center_codes={s['site_code'] for s in centers}
    def add(site,scope,code,field,value,method,bucket='GENERAL',basis='ESTIMATED',url=None,low=None,high=None):
        if site not in center_codes:return
        out.append(dict(site_code=site,scope_type=scope,scope_code=code,field_name=field,bucket=bucket,value=value,method=method,basis=basis,source_url=url,low_value=low,high_value=high,public_visible=True,active=True,expected_version=0,reviewer='planning-bootstrap-2026-10-13'))
    announced={
      'SGC_GUNSAN':(60,'https://www.ktcloud.com/media/press/20260929084129950?lan=kor','1단계60MW 발표를 수전 규모로 가정. 장기300MW 확장 제외'),
      'SKB_GASAN':(46,'https://biz.skbroadband.com/page.do?menu_id=P06010100','가산46MW 발표를 수전 규모로 가정. IT·수전 경계 미검증'),
      'SK_AWS_ULSAN':(103,'https://news.sktelecom.com/226214','외부 기고의 전체103MW 발표를 수전으로 가정. SKT 공식 제원 확정 아님'),
    }
    for s in centers:
        code=s['site_code'];detail=data['details'].get(code,{})
        if code in announced:continue
        # A single whole-site project can size the center; do not add or distribute its phases.
        projects=detail.get('projects',[])
        candidates=[cap for cap in detail.get('capacities',[]) if cap.get('capacity_type_code')=='ANNOUNCED_UNCLASSIFIED_MW'
                    and cap.get('normalized_value_mw') is not None and not cap.get('aggregation_excluded')
                    and (cap.get('effective_to') is None or str(cap['effective_to'])>=REVIEW_DATE)
                    and (cap['scope_type']=='SITE' or cap['scope_type']=='PROJECT' and len(projects)==1)]
        if candidates:
            cap=max(candidates,key=lambda x:str(x.get('published_at') or ''))
            announced[code]=(float(cap['normalized_value_mw']),cap.get('document_url'),'공개 발표 규모를 수전으로 해석한 작업 가정. IT·수전 경계 미검증; 확정 공급과 구분')
    for s in centers:
        code=s['site_code'];detail=data['details'].get(code,{})
        for bucket,prefix in [('OPERATING','operating'),('DEVELOPMENT','development')]:
            if s.get('lifecycle_group') not in ({'OPERATING','MIXED'} if bucket=='OPERATING' else {'DEVELOPMENT','MIXED'}):continue
            grid=s.get(prefix+'_grid_intake_mw');it=s.get(prefix+'_it_load_mw');url=s.get('commercial_source_url') or s.get('facility_source_url')
            if grid is None and code in announced:
                grid,url,note=announced[code];add(code,'SITE',code,'GRID_INTAKE_MW',grid,note,bucket,url=url,low=grid*0.8,high=grid*1.2)
            if it is None:
                if grid is not None:
                    grid=float(grid);it=round(grid/PUE,3);method=f'수전/발표 규모{grid:g}MW ÷ 환산계수1.5 가정. 실제 PUE·피크 설계부하·입주율 미확인. 범위는 계수1.8~1.3 적용'
                    low=round(grid/1.8,3);high=round(grid/1.3,3)
                elif code=='KT_NAMGURO':
                    it=2.07;low=1.38;high=3.45;url='https://www.kt-idc.com/ktidc/viewktidc_introduce_total?idcType=namguro';method='공식 수용345랙 × 가정6kW/랙 =2.07MW. 4~10kW/랙 범위; 현재 설치·점유 용량 아님'
                elif median is not None:
                    it=median;low=round(median*0.25,3);high=round(median*2,3);method=f'시설 제원 미확보 시 임시 시나리오: 원장 공개 운영 IT 표본{len(sample)}곳 중앙값{median:g}MW. 개별 센터 규모 검증 전 넓은0.25~2배 범위. 센터별 사실값 아님';url=None
                else:continue
                add(code,'SITE',code,'IT_LOAD_MW',it,method,bucket,url=url,low=low,high=high)
        for p in detail.get('projects',[]):
            if p.get('status_code') in {'OPERATING','ON_HOLD','CANCELLED'}:continue
            phases=[ph for ph in detail.get('phases',[]) if ph['project_code']==p['project_code']]
            for unit in phases or [p]:
                scope='PHASE' if unit.get('phase_code') else 'PROJECT';target=unit.get('phase_code') or p['project_code']
                if unit.get('rfs_date') or unit.get('planned_rfs_period') or unit.get('planned_rfs_date'):continue
                completion=unit.get('planned_completion_period')
                if completion:
                    if len(completion)==7 and '-Q' not in completion:
                        y,m=map(int,completion.split('-'));n=y*12+m-1+6;period=f'{n//12}-Q{(n%12)//3+1}'
                        method=f'준공 예정{completion} + 가동 준비6개월 가정. 계약상 RFS 확정 아님'
                    else:period=completion;method='준공 예정 기간을 서비스 개시의 초기 가정으로 사용. 실제 RFS 차이 담당자 수정 필요'
                else:
                    years={'READY':1,'CONSTRUCTION':2,'PERMITTING':3,'POWER_SECURED':3,'SITE_SECURED':3,'IDEA':4}.get(unit.get('status_code'),3)
                    period=str(2026+years);method=f'{REVIEW_DATE} 기준 단계별 최초 시나리오: {unit.get("status_code")} +{years}년. 공식 일정 미공개, 담당자 수정 대상'
                add(code,scope,target,'RFS_PERIOD',period,method)
    # Specific phase reports take precedence over generic campus assumptions.
    add('LGU_PAJU','PHASE','LGU_PAJU_PH1','IT_LOAD_MW',40,'KB증권이 제시한 파주1동 IT 약40MW. 운영사 IT 제원과 교차 확인 전 발표값','DEVELOPMENT','ANNOUNCED','https://kbthink.com/securities-view.html?docId=20260811152537520K',35,45)
    add('SGC_GUNSAN','PHASE','SGC_GUNSAN_PH1','GRID_INTAKE_MW',60,'1단계60MW를 수전으로 해석한 계획 가정','DEVELOPMENT','ESTIMATED',announced['SGC_GUNSAN'][1],48,72)
    add('SGC_GUNSAN','PHASE','SGC_GUNSAN_PH1','IT_LOAD_MW',40,'1단계 발표60MW ÷ 환산계수1.5 가정. IT·수전 기준 교차 검증 필요','DEVELOPMENT','ESTIMATED',announced['SGC_GUNSAN'][1],33.333,46.154)
    add('SK_AWS_ULSAN','PHASE','SK_AWS_ULSAN_PH1','IT_LOAD_MW',27.333,'외부 기고1차41MW를 수전으로 가정 ÷1.5. SKT 공식 IT 제원 아님','DEVELOPMENT','ESTIMATED',announced['SK_AWS_ULSAN'][1],22.778,31.538)
    add('SK_AWS_ULSAN','PHASE','SK_AWS_ULSAN_PH1','RFS_PERIOD','2027-11','SKT 뉴스룸 외부 기고의1차 가동2027년11월. 공식2027년 목표보다 상세한 발표값','GENERAL','ANNOUNCED',announced['SK_AWS_ULSAN'][1])
    # One whole-project schedule row can use a working project total without distributing it to multiple phases.
    guro=next((r for r in out if r['site_code']=='SKHORIZON_GURO' and r['field_name']=='IT_LOAD_MW' and r['scope_type']=='SITE'),None)
    if guro:add('SKHORIZON_GURO','PHASE','SKHORIZON_GURO_PH1','IT_LOAD_MW',guro['value'],guro['method']+' · 전체 사업 일정 행 기준','DEVELOPMENT',low=guro['low_value'],high=guro['high_value'])
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--refine-bootstrap',action='store_true');a=p.parse_args();load_env_file();e=create_engine(resolve_database_url())
    try:
        data=build_payload(PublicRepository(e));items=proposals(data);saved=0;skipped=0;refined=0
        with e.connect() as c:
            tx=c.begin()
            try:
                for d in items:
                    exists=c.execute(text('SELECT pv.* FROM planning_value pv JOIN dc_site s USING(site_id) WHERE s.site_code=:site_code AND scope_type=:scope_type AND scope_code=:scope_code AND field_name=:field_name AND bucket=:bucket'),d).mappings().first()
                    if exists:
                        if a.refine_bootstrap and exists['active'] and exists['basis']=='ESTIMATED' and exists['updated_by']==d['reviewer'] and exists['method'].startswith('시설 제원 미확보') and exists['method']!=d['method']:
                            write_value(c,{**d,'expected_version':exists['version']});refined+=1
                        else:skipped+=1
                        continue
                    write_value(c,d);saved+=1
                if a.apply:tx.commit()
                else:tx.rollback()
            except Exception:tx.rollback();raise
        print(json.dumps({'applied':a.apply,'new_working_values':saved,'refined_bootstrap':refined,'preserved_existing':skipped}))
    finally:e.dispose()
if __name__=='__main__':raise SystemExit(main())
