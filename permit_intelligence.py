"""Public permit and infrastructure facts, reconciled separately from the center master."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import re
import unicodedata

from namepf_normalize import normalize, number, iso_date

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / 'data/reference/namepf_intelligence.json'
SOURCE_URL = 'https://dc.namepf.com/data/dash.json'
PROVINCES = {'서울특별시':'서울','서울시':'서울','부산광역시':'부산','대구광역시':'대구','인천광역시':'인천','광주광역시':'광주','대전광역시':'대전','울산광역시':'울산','세종특별자치시':'세종','경기도':'경기','강원특별자치도':'강원','강원도':'강원','충청북도':'충북','충청남도':'충남','전북특별자치도':'전북','전라북도':'전북','전라남도':'전남','경상북도':'경북','경상남도':'경남','제주특별자치도':'제주'}


def region_key(value):
    value = str(value or '').strip()
    return PROVINCES.get(value, value)


def address_key(value):
    value = unicodedata.normalize('NFKC', str(value or '')).strip()
    for long, short in sorted(PROVINCES.items(), key=lambda p:-len(p[0])):
        if value.startswith(long):
            value = short + value[len(long):]
            break
    return re.sub(r'[\s,()]', '', value).lower()


def name_key(value):
    value = unicodedata.normalize('NFKC', str(value or '')).lower()
    value = re.sub(r'데이터\s*센터|data\s*cent[er]+|신축공사|증축|대수선', '', value)
    value = re.sub(r'\bai\b|(?<=[가-힣])ai(?=\s|데이터|$)', '', value)
    return re.sub(r'[^가-힣a-z0-9]', '', value)


def connect(items, sites):
    """An exact address links the row; a similar name only suggests a review target."""
    result = []
    for item in items:
        row = copy.deepcopy(item)
        key = address_key(row.get('address'))
        exact = [s for s in sites if key and key == address_key(s.get('address_standard'))]
        name = name_key(row.get('building_name'))
        hints = [s for s in sites if len(name)>4 and name == name_key(s.get('site_name')) and region_key(s.get('sido')) == region_key(row.get('region'))]
        choices = exact or hints
        status = 'ADDRESS_MATCH' if len(exact)==1 else 'AMBIGUOUS_ADDRESS' if len(exact)>1 else 'NAME_HINT' if hints else 'UNLINKED'
        row['connection'] = {'status':status,'site_code':exact[0]['site_code'] if len(exact)==1 else None,
            'candidates':[{'site_code':s['site_code'],'site_name':s['site_name']} for s in choices],
            'method':'정규화한 주소 전체 일치' if exact else '동일 지역·이름 일치 · 주소 확인 필요' if hints else '원장 주소·사업자 대조 필요'}
        row['canonical_region'] = region_key(row.get('region'))
        result.append(row)
    return result


def infrastructure(document):
    permits = document.get('permits') or {}
    hr = permits.get('headroom') or {}
    subs = {str(k):number(v) for k,v in (hr.get('subs') or {}).items()}
    area_subs = hr.get('sido') or {}
    kepco = document.get('kepco') or {}
    power = document.get('power') or {}
    months, hours = kepco.get('months') or [], kepco.get('hours') or []
    recent = months[-12:]
    valid_window = len(recent)==12 and len(months)==len(hours)
    if valid_window:
        try:
            period_ids = [int(m[:4])*12+int(m[5:7]) for m in recent]
            valid_window = all(re.fullmatch(r'\d{4}-\d{2}', m) and 1<=int(m[5:7])<=12 for m in recent) and all(b-a==1 for a,b in zip(period_ids,period_ids[1:]))
        except (TypeError,ValueError):
            valid_window = False
    regions = []
    for name in sorted(set(area_subs) | set(kepco.get('sido') or {}) | set(power.get('self') or {})):
        station_names = sorted(set(area_subs.get(name) or []))
        values = [subs[n] for n in station_names if n in subs and subs[n] is not None]
        usage = (kepco.get('sido') or {}).get(name) or []
        avg = None
        if valid_window and len(usage)==len(months):
            hs = [number(x) for x in hours[-12:]]
            us = [number(x) for x in usage[-12:]]
            if all(x is not None for x in hs+us) and all(h>0 for h in hs):
                avg = round(sum(us)/sum(hs)/1000,3)
        regions.append({'name':name,'station_group_ids':station_names,'station_groups':len(station_names),
            'known_groups':len(values),'available_groups':sum(v>0 for v in values),
            'headroom_mw':sum(values) if values else None,
            'ict_average_mw':avg,'ict_period_from':recent[0] if valid_window else None,'ict_period_to':recent[-1] if valid_window else None,
            'self_sufficiency_pct':number((power.get('self') or {}).get(name)),'self_sufficiency_year':str(power.get('self_year') or '') or None})
    known = [v for v in subs.values() if v is not None]
    return {'source_status':'SOURCE_REPORTED','headroom_checked_on':iso_date(hr.get('updated')),
        'regions':regions,'national_headroom_mw':sum(known) if known else None,
        'national_station_groups':len(subs),'national_known_groups':len(known),
        'national_available_groups':sum(v>0 for v in known),
        'unit_note':'정보통신업 kWh ÷ 실제 집계시간 ÷ 1,000 = 기간 평균 MW. DC 전용 IT Load와 별도.',
        'headroom_note':'동일 변전소 그룹은 전국 합계에서 한 번만 집계. 지역 관할 합계끼리는 더하지 않음.',
        'primary_sources':[{'name':'한국전력 전력데이터 개방포털','url':'https://bigdata.kepco.co.kr/'},{'name':'전력거래소 EPSIS','url':'https://epsis.kpx.or.kr/epsisnew/'}]}


def build(document, previous=None, now=None):
    now = now or datetime.now(timezone.utc).isoformat()
    if not (document.get('permits') or {}).get('complete'):
        raise ValueError('Incomplete permit snapshot')
    normalized = normalize(document,0)
    if not normalized['items']:
        raise ValueError('Empty permit snapshot')
    items = normalized['items']
    if any(not item.get('external_permit_id') for item in items):
        raise ValueError('Missing external permit identifier')
    # Publication contains facts and references, not third-party narrative paragraphs or map assets.
    for item in items:
        item.pop('capacity_note',None)
    result = {'format':'dc-development-intelligence-v1','source_url':SOURCE_URL,'source_name':'NamePF 공개 데이터센터 개발 현황',
        'source_type':'THIRD_PARTY_DASHBOARD','source_built_raw':normalized['source_built_raw'],
        'permits_updated_on':normalized['source_permits_updated_on'],
        'primary_source_url':'https://www.data.go.kr/data/15136267/openapi.do','fact_status':'CANDIDATE',
        'items':items,'infrastructure':infrastructure(document)}
    result['fact_digest'] = hashlib.sha256(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    old_items = {r['external_permit_id']:r for r in (previous or {}).get('items',[])}
    fresh_items = {r['external_permit_id']:r for r in items}
    result['collection'] = {'status':'SUCCESS','attempted_at':now,'last_success_at':now,
        'source_changed':result['fact_digest']!=(previous or {}).get('fact_digest'),
        'added_records':len(set(fresh_items)-set(old_items)),
        'changed_records':sum({a:b for a,b in old_items[k].items() if a!='capacity_checked_on'}!={a:b for a,b in v.items() if a!='capacity_checked_on'} for k,v in fresh_items.items() if k in old_items),
        'removed_records':len(set(old_items)-set(fresh_items))}
    return result


def load_reference(path=REFERENCE):
    if not path.exists():
        return None
    dataset=json.loads(path.read_text(encoding='utf-8'))
    if dataset.get('format')!='dc-development-intelligence-v1' or not isinstance(dataset.get('items'),list):
        raise ValueError('Invalid development intelligence file')
    return dataset


def augment(payload, dataset):
    result=dict(payload)
    if dataset is None:
        return result
    intelligence=copy.deepcopy(dataset)
    intelligence['items']=connect(dataset['items'],payload.get('sites',[]))
    items=intelligence['items']
    parcels={r['external_parcel_hint'] for r in items if r.get('external_parcel_hint')}
    matches=[r for r in items if r['connection']['status']=='ADDRESS_MATCH']
    intelligence['summary']={'permit_records':len(items),'parcel_groups':len(parcels),
        'stages':dict(Counter(r.get('permit_stage') or '미확인' for r in items)),
        'address_matched_records':len(matches),'linked_master_sites':len({r['connection']['site_code'] for r in matches}),
        'name_hint_records':sum(r['connection']['status']=='NAME_HINT' for r in items),
        'ambiguous_records':sum(r['connection']['status']=='AMBIGUOUS_ADDRESS' for r in items),
        'unlinked_records':sum(r['connection']['status']=='UNLINKED' for r in items),
        'area_review_records':sum((r.get('areas_sqm',{}).get('dc_use_ratio_pct') or 0)>100 for r in items),
        'coordinate_representative_records':sum(r.get('location',{}).get('verification')=='ADMINISTRATIVE_REPRESENTATIVE_POINT' for r in items)}
    result['development_intelligence']=intelligence
    return result
