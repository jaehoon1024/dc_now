import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from permit_intelligence import augment,build,connect,infrastructure
from src30_collect_permit_intelligence import refresh,save


def document():
    return {'built':'2026-10-13 10:30','permits':{'complete':True,'updated':'20261012',
        'rows':[{'id':'P1','site':'PARCEL1','nm':'Test DC','addr':'경기도 김포시 구래동 6877-9','sd':'경기','sg':'김포시','kind':'신축','stage':'준공','pms':'2020-01-01','apr':'2026-02-01','ll':[126.5,37.5],'llp':'dong','area':100,'dcArea':110,'cap':{'mw':40,'basis':'미표기','checked':'2026-10-13'}}],
        'headroom':{'updated':'2026-10-13','subs':{'shared':100,'zero':0},'sido':{'서울':['shared'],'경기':['shared','zero']}}},
        'kepco':{'months':[f'2025-{n:02}' for n in range(1,13)],'hours':[720]*12,'sido':{'서울':[720000]*12}},
        'power':{'self_year':'2025','self':{'서울':7}}}


class PermitIntelligenceTests(unittest.TestCase):
    def test_zero_unknown_capacity_and_representative_coordinates_remain_distinct(self):
        d=build(document())
        r=d['items'][0]
        self.assertEqual(r['capacities'][0]['type'],'ANNOUNCED_UNCLASSIFIED_MW')
        self.assertEqual(r['location']['verification'],'ADMINISTRATIVE_REPRESENTATIVE_POINT')
        self.assertEqual(r['location']['longitude'],126.5)
        self.assertIsNone(r['rfs_on'])
        self.assertEqual(r['dates']['building_approved_on'],'2026-02-01')
        self.assertAlmostEqual(r['areas_sqm']['dc_use_ratio_pct'],110)
        self.assertNotIn('capacity_note',r)

    def test_exact_addresses_link_and_shared_campuses_require_review(self):
        item=build(document())['items'][0]
        site={'site_code':'A','site_name':'Different brand','address_standard':'경기 김포시 구래동 6877-9','sido':'경기도'}
        self.assertEqual(connect([item],[site])[0]['connection']['status'],'ADDRESS_MATCH')
        duplicate={**site,'site_code':'B'}
        linked=connect([item],[site,duplicate])[0]['connection']
        self.assertEqual(linked['status'],'AMBIGUOUS_ADDRESS')
        self.assertIsNone(linked['site_code'])
        self.assertEqual(len(linked['candidates']),2)
        self.assertEqual(connect([item],[{**site,'address_standard':'경기 김포시 구래동 6877-8'}])[0]['connection']['status'],'UNLINKED')

    def test_similar_name_never_overrides_different_address(self):
        item=build(document())['items'][0]
        site={'site_code':'A','site_name':'Test DC','address_standard':'경기 김포시 다른동 1','sido':'경기도'}
        relation=connect([item],[site])[0]['connection']
        self.assertEqual(relation['status'],'NAME_HINT')
        self.assertIsNone(relation['site_code'])

    def test_master_and_planning_values_are_not_rewritten_by_permit_rows(self):
        payload={'sites':[{'site_code':'A','site_name':'Test DC','address_standard':'경기 김포시 구래동 6877-9','lifecycle_group':'DEVELOPMENT','operating_it_load_mw':None}], 'planning_values':[{'value':26}]}
        before=copy.deepcopy(payload)
        result=augment(payload,build(document()))
        self.assertEqual(payload,before)
        self.assertEqual(result['sites'],before['sites'])
        self.assertEqual(result['planning_values'],before['planning_values'])
        self.assertEqual(result['development_intelligence']['summary']['linked_master_sites'],1)
        self.assertEqual(result['sites'][0]['lifecycle_group'],'DEVELOPMENT')

    def test_region_headroom_is_deduplicated_and_kwh_is_converted_to_average_mw(self):
        data=infrastructure(document())
        self.assertEqual(data['national_headroom_mw'],100)
        self.assertEqual(data['national_available_groups'],1)
        self.assertEqual(data['national_known_groups'],2)
        regions={r['name']:r for r in data['regions']}
        self.assertEqual(regions['서울']['ict_average_mw'],1)
        self.assertEqual(regions['경기']['headroom_mw'],100)
        self.assertEqual(regions['경기']['available_groups'],1)
        self.assertIsNone(regions['경기']['ict_average_mw'])

    def test_incomplete_months_never_extrapolate_usage(self):
        for mode in ('missing','zero_hours','bad_month'):
            d=document()
            if mode=='missing':d['kepco']['sido']['서울'][0]=None
            if mode=='zero_hours':d['kepco']['hours'][0]=0
            if mode=='bad_month':d['kepco']['months'][-1]='2025-13'
            self.assertIsNone(next(r for r in infrastructure(d)['regions'] if r['name']=='서울')['ict_average_mw'])

    def test_identical_and_check_date_only_updates_do_not_count_as_changed_facts(self):
        first=build(document())
        d=document();d['permits']['rows'][0]['cap']['checked']='2026-10-14'
        second=build(d,first)
        self.assertEqual(second['collection']['added_records'],0)
        self.assertEqual(second['collection']['changed_records'],0)
        d['permits']['rows'][0]['cap']['mw']=50
        self.assertEqual(build(d,second)['collection']['changed_records'],1)

    def test_failed_refresh_preserves_last_success_and_records_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'reference.json';good=build(document());save(target,good)
            with patch('src30_collect_permit_intelligence.urlopen',side_effect=TimeoutError('private diagnostic')):
                self.assertEqual(refresh(target),0)
            saved=json.loads(target.read_text())
            self.assertEqual(saved['items'],good['items'])
            self.assertEqual(saved['collection']['last_success_at'],good['collection']['last_success_at'])
            self.assertEqual(saved['collection']['status'],'FAILED_KEPT_PREVIOUS')
            self.assertNotIn('private diagnostic',target.read_text())

    def test_invalid_snapshots_never_replace_good_data(self):
        for mode in ('incomplete','empty','missing_id','duplicate'):
            d=document()
            if mode=='incomplete':d['permits']['complete']=False
            if mode=='empty':d['permits']['rows']=[]
            if mode=='missing_id':d['permits']['rows'][0].pop('id')
            if mode=='duplicate':d['permits']['rows'].append(copy.deepcopy(d['permits']['rows'][0]))
            with self.assertRaises(ValueError):build(d)


if __name__=='__main__':unittest.main()
