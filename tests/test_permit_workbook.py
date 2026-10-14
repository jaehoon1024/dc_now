import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from xml.sax.saxutils import escape
import json

from permit_workbook import COLUMNS, normalize_row, reconcile, import_workbook, attach_workbook, sheet_rows, workbook_date
from permit_intelligence import load_reference


def values(**overrides):
    fields={'건물명':'테스트센터','구분':'신축','시도':'경기','시군구':'김포시','주소':'경기도 김포시 구래동 1','단계':'공사 중','허가일':'2025-01-01','연면적(㎡)':'100','데이터센터 층 연면적(㎡)':'110','대지면적(㎡)':'50','용량(MW)':'20','용량 기준':'IT','용적률(%)':'0','용도지역':'준공업지역','대장 변경일':'2026-10-14','관할 변전소 추가 여유(MW)':'–'}
    fields.update(overrides)
    return {i:fields.get(k,'') for i,k in enumerate(COLUMNS)}


def item(identity='P1',gross=100,approved=None):
    f=normalize_row(values())
    return {'external_permit_id':identity,'address':f['address'],'building_name':f['building_name'],'permit_kind':'신축','permit_stage':'공사 중',
        'dates':{**f['dates'],'building_approved_on':approved},'areas_sqm':{**f['areas_sqm'],'gross':gross},
        'capacities':[{'type':'IT_LOAD_MW','mw':20}],'rfs_on':None,'location':{'verification':'UNVERIFIED'}}


def snapshot():
    facts=normalize_row(values())
    return {'format':'dc-permit-workbook-v1','source_name':'test.xlsx','source_sha256':'test-hash','source_collected_at_raw':'2026-10-14 07:45 KST','source_scope':'test','summary':{'workbook_rows':1},'items':[{'external_permit_id':'P1','source_row':2,'match_method':'주소 일치','facts':facts}],'pending_items':[]}


class PermitWorkbookTests(unittest.TestCase):
    def test_it_basis_zero_and_date_semantics(self):
        f=normalize_row(values(**{'사용승인일':'2026-01-01'}))
        self.assertEqual(f['floor_area_ratio_pct'],0)
        self.assertEqual(f['headroom_mw'],0)
        self.assertEqual(f['dates']['building_approved_on'],'2026-01-01')
        from permit_workbook import core_differences
        self.assertEqual(core_differences(item(),normalize_row(values())),[])
        self.assertIsNone(item()['rfs_on'])
        self.assertEqual(workbook_date('45292'),'2024-01-01')
        with self.assertRaises(ValueError):workbook_date('unknown')

    def test_same_address_and_date_disambiguated_by_area_and_approval(self):
        a=item('P1',100,'2026-01-01');b=item('P2',200,'2026-02-01')
        rows=[(2,values(**{'사용승인일':'2026-01-01'})),(3,values(**{'연면적(㎡)':'200','사용승인일':'2026-02-01'}))]
        matched,pending,n=reconcile(rows,{'items':[a,b]})
        self.assertEqual([x['external_permit_id'] for x in matched],['P1','P2'])
        self.assertEqual(pending,[]);self.assertEqual(n,2)

    def test_ambiguous_or_duplicate_rows_never_attach_arbitrarily(self):
        matched,pending,n=reconcile([(2,values())],{'items':[item('P1'),item('P2')]})
        self.assertEqual(matched,[]);self.assertEqual(len(pending),1)
        matched,pending,n=reconcile([(2,values()),(3,values())],{'items':[item()]})
        self.assertEqual(len(matched),1);self.assertEqual(len(pending),1)

    def test_workbook_facts_remain_after_live_refresh_and_do_not_overwrite_new_values(self):
        baseline={'items':[item()],'collection':{'status':'SUCCESS'}}
        baseline['items'][0]['permit_stage']='준공'
        before=copy.deepcopy(baseline)
        enriched=attach_workbook(baseline,snapshot())
        self.assertEqual(baseline,before)
        self.assertEqual(enriched['items'][0]['permit_stage'],'준공')
        self.assertEqual(enriched['items'][0]['workbook_reference']['facts']['permit_stage'],'공사 중')
        self.assertEqual(enriched['workbook_import']['current_core_changed_records'],1)
        self.assertEqual(len(enriched['items']),1)
        self.assertEqual(enriched['items'][0]['workbook_reference']['source_row'],2)

    def test_removed_live_permits_are_not_resurrected(self):
        enriched=attach_workbook({'items':[]},snapshot())
        self.assertEqual(enriched['items'],[])
        self.assertEqual(enriched['workbook_import']['unavailable_records'],1)

    def test_reference_loading_can_skip_supplement_for_collector(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ref=root/'live.json';workbook=root/'workbook.json'
            ref.write_text(json.dumps({'format':'dc-development-intelligence-v1','items':[item()]}))
            workbook.write_text(json.dumps(snapshot()))
            with patch('permit_intelligence.REFERENCE',ref),patch('permit_workbook.WORKBOOK_REFERENCE',workbook):
                self.assertIn('workbook_reference',load_reference(ref)['items'][0])
                self.assertNotIn('workbook_reference',load_reference(ref,include_workbook=False)['items'][0])

    def test_sensitive_links_are_rejected(self):
        f=normalize_row(values(**{'용량 출처':'https://example.com/?api_key=do-not-export'}))
        self.assertIsNone(f['capacity_source_url'])

    def test_inline_xlsx_source_and_row_provenance(self):
        def column(index):
            out=''
            while index:
                index,r=divmod(index-1,26);out=chr(65+r)+out
            return out
        def row(index,data):
            return '<row r="'+str(index)+'">'+''.join('<c r="'+column(i+1)+str(index)+'" t="inlineStr"><is><t>'+escape(str(v))+'</t></is></c>' for i,v in data.items())+'</row>'
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'test.xlsx'
            with ZipFile(target,'w') as archive:
                archive.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="인허가 목록" r:id="rId1"/></sheets></workbook>')
                archive.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
                archive.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+row(1,dict(enumerate(COLUMNS)))+row(2,values())+'</sheetData></worksheet>')
            result=import_workbook(target,{'items':[item()]})
            self.assertEqual(result['summary']['matched_records'],1)
            self.assertEqual(result['summary']['core_changed_records'],0)
            self.assertEqual(result['items'][0]['source_row'],2)
            self.assertEqual(len(result['source_sha256']),64)


if __name__=='__main__':unittest.main()
