#!/usr/bin/env python3
"""Normalize a supplied public NamePF snapshot into review candidates; no network or DB."""
import argparse
import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

SOURCE = 'https://dc.namepf.com/data/dash.json'


def number(value):
    if value is None or isinstance(value, bool) or value == '':
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def text(value):
    return str(value).strip() if isinstance(value, (str, int, float)) else ''


def public_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        fields = [k.lower() for k, _ in parse_qsl(parsed.query)]
        if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password:
            return None
        if any(re.search(r'api_?key|service_?key|token|password|secret|signature|credential|authorization', key) for key in fields):
            return None
        if any(key.lower()=='key' and value.startswith('AIza') for key,value in parse_qsl(parsed.query)):
            return None
        return value
    except ValueError:
        return None


def iso_date(value):
    raw = text(value)
    if not raw:
        return None
    if re.fullmatch(r'\d{8}', raw):
        raw = raw[:4] + '-' + raw[4:6] + '-' + raw[6:]
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def links(items):
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        url = public_url(item.get('u'))
        if url:
            result.append({'title':text(item.get('t')), 'publisher':text(item.get('o') or item.get('src')), 'published_on':iso_date(item.get('d')), 'url':url})
    return result


def candidate(row, checked_on):
    if not isinstance(row, dict):
        raise ValueError('Permit row must be an object')
    warnings = []
    source_id, address = text(row.get('id')), text(row.get('addr'))
    if not source_id:
        warnings.append('외부 허가 ID 미확인 · 원출처 식별자 보완 필요')
    if not address:
        warnings.append('주소 미확인')
    identity = source_id or hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    area, dc_area = number(row.get('area')), number(row.get('dcArea'))
    ratio = dc_area / area * 100 if area is not None and area > 0 and dc_area is not None else None
    if ratio is not None and ratio > 100:
        warnings.append('데이터센터 용도 면적이 총 연면적을 초과 · 원대장 대조 필요')

    dates = {}
    for raw_key, key in [('pms','permit_on'), ('stc','construction_started_on'), ('sched','construction_scheduled_on'), ('apr','building_approved_on')]:
        dates[key] = iso_date(row.get(raw_key))
        if row.get(raw_key) and dates[key] is None:
            warnings.append(f'{key} 날짜 형식 확인 필요')
        if raw_key != 'sched' and dates[key] and dates[key] > checked_on:
            warnings.append(f'{key} 실제 일자가 확인일 이후 · 원문 확인 필요')

    cap = row.get('cap') or {}
    if not isinstance(cap, dict):
        raise ValueError('Capacity schema changed')
    mw, it = number(cap.get('mw')), number(cap.get('it'))
    basis = text(cap.get('basis'))
    reported_type = 'GRID_INTAKE_MW' if '수전' in basis else 'IT_LOAD_MW' if re.fullmatch(r'IT(?:\s*(?:LOAD|기준|부하))?', basis.upper()) else 'ANNOUNCED_UNCLASSIFIED_MW'
    capacities = []
    source_links = links(cap.get('src'))
    if cap.get('none') and (mw is not None or it is not None):
        warnings.append('용량 미확인 플래그와 수치가 동시에 존재')
    if mw is not None:
        capacities.append({'type':reported_type,'mw':mw,'source_basis':basis or None,'review_status':'CANDIDATE','scope_status':'UNCONFIRMED','evidence':source_links})
        if reported_type == 'ANNOUNCED_UNCLASSIFIED_MW':
            warnings.append('발표 MW의 수전/IT 기준 미확인')
    if it is not None and not (reported_type == 'IT_LOAD_MW' and it == mw):
        capacities.append({'type':'IT_LOAD_MW','mw':it,'source_basis':'명시 IT 필드','review_status':'CANDIDATE','scope_status':'UNCONFIRMED','evidence':source_links})
    if not capacities:
        warnings.append('용량 원문 확보 필요')

    location = {'longitude':None,'latitude':None,'source_precision':text(row.get('llp')) or None,'verification':'UNVERIFIED'}
    ll = row.get('ll')
    if isinstance(ll, list) and len(ll) == 2:
        try:
            if any(isinstance(v,bool) for v in ll):
                raise ValueError()
            lon, lat = float(ll[0]), float(ll[1])
            if math.isfinite(lon) and math.isfinite(lat) and 124 <= lon <= 132 and 32 <= lat <= 40:
                location.update(longitude=lon,latitude=lat)
            else:
                warnings.append('경위도 순서 또는 한국 지도 범위 확인 필요')
        except (TypeError,ValueError):
            warnings.append('좌표 형식 확인 필요')
    if location['source_precision'] in {'sgg','dong','ri'}:
        location['verification'] = 'ADMINISTRATIVE_REPRESENTATIVE_POINT'
        warnings.append('행정구역 대표점 · 센터 정확 좌표로 사용하지 않음')
    if location['longitude'] is None:
        warnings.append('좌표 미확인')

    hr = row.get('hr') or {}
    hr = hr if isinstance(hr,dict) else {}
    subs = hr.get('subs') or {}
    return {
        'candidate_id':'NAMEPF_PERMIT:' + identity,
        'external_permit_id':source_id or None,
        'external_parcel_hint':text(row.get('site')) or None,
        'building_name':text(row.get('nm')) or None,
        'address':address or None,
        'region':text(row.get('sd')) or None,
        'district':text(row.get('sg')) or None,
        'permit_kind':text(row.get('kind')) or None,
        'permit_stage':text(row.get('stage')) or None,
        'dates':dates,
        'rfs_on':None,
        'areas_sqm':{'gross':area,'dc_use':dc_area,'land':number(row.get('plat')),'dc_use_ratio_pct':ratio},
        'location':location,
        'capacities':capacities,
        'capacity_note':text(cap.get('note')) or None,
        'capacity_checked_on':iso_date(cap.get('checked')),
        'infrastructure_context':{'substation_headroom_mw':{text(k):number(v) for k,v in subs.items()} if isinstance(subs,dict) else {},'reported_headroom_sum_mw':number(hr.get('sum')),'meaning':'지역·변전소 공급 여유 · 센터 확보 전력과 별도'},
        'news':links(row.get('news')),
        'commercial_scope':'REVIEW_REQUIRED',
        'review_status':'CANDIDATE',
        'quality_warnings':warnings,
    }


def normalize(document, limit=5):
    if not isinstance(document,dict) or not isinstance(document.get('permits'),dict) or not isinstance(document['permits'].get('rows'),list):
        raise ValueError('Expected permits.rows array; recheck the public schema')
    if limit < 0:
        raise ValueError('Limit must be zero or positive')
    rows=document['permits']['rows']
    checked=datetime.now(timezone.utc)
    chosen=rows if limit == 0 else rows[:limit]
    records=[candidate(row,checked.date().isoformat()) for row in chosen]
    ids=[r['candidate_id'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate permit IDs; examine amendment/history rows before merging')
    return {'format':'dc-namepf-candidates-v1','source_url':SOURCE,'source_type':'THIRD_PARTY_DASHBOARD','source_built_raw':text(document.get('built')) or None,'source_permits_updated_on':iso_date(document['permits'].get('updated')),'checked_at':checked.isoformat(),'available_input_rows':len(rows),'candidate_count':len(records),'application_status':'NOT_APPLIED','items':records}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--limit',type=int,default=5,help='Default sample: 5; 0 normalizes all supplied rows')
    args=parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise ValueError('Input and output must be different files')
    result=normalize(json.loads(args.input.read_text(encoding='utf-8')),args.limit)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(f"Prepared {result['candidate_count']} permit candidates; database and publishing unchanged.")


if __name__ == '__main__':
    main()
