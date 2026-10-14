"""Read a supplied permit workbook and attach traceable facts without replacing master data."""
from __future__ import annotations

from collections import defaultdict
import copy
from datetime import date, timedelta
import hashlib
from pathlib import Path
import re
from urllib.parse import urljoin
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from namepf_normalize import iso_date, number, public_url

WORKBOOK_REFERENCE = Path(__file__).resolve().parent / 'data/reference/permit_workbook_20261014.json'
NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
COLUMNS = ['건물명','구분','시도','시군구','읍면동 · 리','주소','단계','허가일','착공일','착공 예정일','사용승인일','연면적(㎡)','데이터센터 층 연면적(㎡)','데이터센터 비중(%)','대지면적(㎡)','용적률(%)','용도지역','용량(MW)','IT 용량(MW)','용량 기준','용량 원문','용량 출처','관할 변전소 추가 여유(MW)','관할 변전소별 여유','관련 기사 수','최근 기사','최근 기사 날짜','최근 기사 링크','지도','대장 변경일']


def sheet_rows(path):
    """Read cached values only; formulas and external links are never executed."""
    with ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 30_000_000:
            raise ValueError('Workbook exceeds size limit')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in si.findall('.//s:t',NS)) for si in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        relationships = {r.get('Id'):r.get('Target') for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        settings = workbook.find('s:workbookPr',NS)
        if settings is not None and settings.get('date1904') in {'1','true'}:
            raise ValueError('Workbook must use the Excel 1900 date system')
        result = {}
        for sheet in workbook.findall('s:sheets/s:sheet',NS):
            target = relationships[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            entry = target.lstrip('/') if target.startswith('/') else urljoin('xl/',target)
            rows = []
            for row in ET.fromstring(archive.read(entry)).findall('s:sheetData/s:row',NS):
                cells = {}
                for cell in row.findall('s:c',NS):
                    if cell.find('s:f',NS) is not None:
                        raise ValueError('Formula cell requires a values-only export')
                    value = cell.find('s:v',NS)
                    value = value.text if value is not None else ''.join(t.text or '' for t in cell.findall('.//s:t',NS))
                    if cell.get('t') == 's' and value:
                        value = strings[int(value)]
                    letters = re.sub(r'\d','',cell.get('r',''))
                    index = 0
                    for char in letters:
                        index = index*26 + ord(char)-64
                    cells[index-1] = value or ''
                rows.append((int(row.get('r')),cells))
            result[sheet.get('name')] = rows
        return result


def clean(value):
    text = str(value or '').strip()
    return None if text in {'','–','—','(건물명 없음)'} else text


def workbook_date(value):
    value = clean(value)
    if value is None:
        return None
    parsed = iso_date(value.split('T')[0])
    if parsed:
        return parsed
    # This public export uses the Excel 1900 date system if dates are numeric.
    try:
        serial = float(value)
        if 1 <= serial < 80000:
            return (date(1899,12,30)+timedelta(days=int(serial))).isoformat()
    except ValueError:
        pass
    raise ValueError('Invalid workbook date')


def normalize_row(values):
    v = {header:values.get(i,'') for i,header in enumerate(COLUMNS)}
    return {'building_name':clean(v['건물명']),'address':clean(v['주소']),'region':clean(v['시도']),'district':clean(v['시군구']),
        'dong':clean(v['읍면동 · 리']),'permit_kind':clean(v['구분']),'permit_stage':clean(v['단계']),
        'dates':{k:workbook_date(v[h]) for h,k in [('허가일','permit_on'),('착공일','construction_started_on'),('착공 예정일','construction_scheduled_on'),('사용승인일','building_approved_on')]},
        'areas_sqm':{k:number(v[h]) for h,k in [('연면적(㎡)','gross'),('데이터센터 층 연면적(㎡)','dc_use'),('대지면적(㎡)','land')]},
        'reported_dc_use_ratio_pct':number(v['데이터센터 비중(%)']),'floor_area_ratio_pct':number(v['용적률(%)']),
        'zoning':clean(v['용도지역']),'registry_changed_on':workbook_date(v['대장 변경일']),
        'capacity_mw':number(v['용량(MW)']),'it_capacity_mw':number(v['IT 용량(MW)']),
        'capacity_basis':clean(v['용량 기준']),'capacity_quote':clean(v['용량 원문']),'capacity_source_url':public_url(v['용량 출처']),
        'headroom_mw':0.0 if v['관할 변전소 추가 여유(MW)'] == '–' else number(v['관할 변전소 추가 여유(MW)']),
        'headroom_description':clean(v['관할 변전소별 여유']),'article_count':number(v['관련 기사 수']),
        'latest_article':{'title':clean(v['최근 기사']),'published_on':workbook_date(v['최근 기사 날짜']),'url':public_url(v['최근 기사 링크'])},
        'source_map_url':public_url(v['지도'])}


def core_differences(item, facts):
    differences=[]
    for key in ['building_name','address','permit_kind','permit_stage']:
        if facts.get(key) != item.get(key):
            differences.append({'field':key,'workbook':facts.get(key),'current':item.get(key)})
    for group in ['dates','areas_sqm']:
        for key,value in facts.get(group,{}).items():
            existing=item.get(group,{}).get(key)
            if group=='areas_sqm' and value is not None and existing is not None and abs(value-existing)<=0.5:
                continue
            if value != existing:
                differences.append({'field':group+'.'+key,'workbook':value,'current':existing})
    basis = str(facts.get('capacity_basis') or '')
    reported_type = 'GRID_INTAKE_MW' if '수전' in basis else 'IT_LOAD_MW' if re.fullmatch(r'IT(?:\s*(?:LOAD|기준|부하))?',basis.upper()) else 'ANNOUNCED_UNCLASSIFIED_MW'
    for key,kind in [('capacity_mw',reported_type),('it_capacity_mw','IT_LOAD_MW')]:
        value=facts.get(key)
        candidates=[c.get('mw') for c in item.get('capacities',[]) if c.get('type')==kind]
        if value is not None and value not in candidates:
            differences.append({'field':key,'workbook':value,'current':candidates})
    return differences


def reconcile(rows, dataset):
    from permit_intelligence import address_key
    index=defaultdict(list)
    for item in dataset['items']:
        index[(address_key(item.get('address')),item.get('dates',{}).get('permit_on'),item.get('permit_kind'))].append(item)
    matched=[];pending=[];used=set();area_matches=0
    for source_row,values in rows:
        facts=normalize_row(values)
        choices=index[(address_key(facts['address']),facts['dates']['permit_on'],facts['permit_kind'])]
        method='주소·허가일·공사 구분 일치'
        if len(choices)>1:
            choices=[x for x in choices if all(facts['areas_sqm'][k] is not None and x.get('areas_sqm',{}).get(k) is not None and abs(facts['areas_sqm'][k]-x['areas_sqm'][k])<=0.5 for k in ['gross','dc_use','land']) and facts['dates']['building_approved_on']==x.get('dates',{}).get('building_approved_on')]
            method+=' · 면적·사용승인일 대조'
        if len(choices)!=1 or choices[0]['external_permit_id'] in used:
            pending.append({'source_row':source_row,'facts':facts,'reason':'AMBIGUOUS_OR_DUPLICATE' if choices else 'UNLINKED'})
            continue
        item=choices[0];used.add(item['external_permit_id'])
        area_matches+=int('면적' in method)
        matched.append({'external_permit_id':item['external_permit_id'],'source_row':source_row,'match_method':method,'facts':facts,'differences':core_differences(item,facts)})
    return matched,pending,area_matches


def import_workbook(path,dataset):
    sheets=sheet_rows(path)
    data=sheets.get('인허가 목록') or []
    if not data or [data[0][1].get(i) for i in range(len(COLUMNS))] != COLUMNS:
        raise ValueError('Unexpected permit workbook columns')
    info={v.get(0):v.get(1) for _,v in sheets.get('안내',[])}
    matched,pending,area_matches=reconcile(data[1:],dataset)
    if not matched:
        raise ValueError('Workbook contains no matched permit records')
    return {'format':'dc-permit-workbook-v1','source_name':path.name.removeprefix('1-'),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_type':'USER_PROVIDED_PUBLIC_EXPORT','source_url':'https://dc.namepf.com/','source_collected_at_raw':info.get('수집 시각'),
        'source_scope':info.get('대상'),'source_primary_description':info.get('출처'),
        'summary':{'workbook_rows':len(data)-1,'matched_records':len(matched),'pending_records':len(pending),'disambiguated_records':area_matches,
            'core_changed_records':sum(bool(x['differences']) for x in matched)},'items':matched,'pending_items':pending}


def attach_workbook(dataset,workbook):
    if workbook.get('format')!='dc-permit-workbook-v1':
        raise ValueError('Invalid permit workbook reference')
    result=copy.deepcopy(dataset)
    index={x['external_permit_id']:x for x in workbook['items']}
    applied=0;changed=0
    for item in result['items']:
        match=index.get(item['external_permit_id'])
        if not match:
            continue
        facts=copy.deepcopy(match['facts'])
        differences=core_differences(item,facts)
        item['workbook_reference']={'source_name':workbook['source_name'],'source_sha256':workbook['source_sha256'],
            'source_collected_at_raw':workbook['source_collected_at_raw'],'sheet':'인허가 목록','source_row':match['source_row'],
            'match_method':match['match_method'],'facts':facts,'current_differences':differences}
        applied+=1;changed+=bool(differences)
    result['workbook_import']={k:copy.deepcopy(workbook[k]) for k in ['source_name','source_sha256','source_collected_at_raw','source_scope','summary']}
    result['workbook_import'].update({'applied_records':applied,'current_core_changed_records':changed,'unavailable_records':len(index)-applied})
    return result
