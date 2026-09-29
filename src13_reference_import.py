#!/usr/bin/env python3
"""Validate and import company, participation, capacity, and evidence CSVs."""
from __future__ import annotations
import argparse, csv, re, sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from src04_rss_collector import load_env_file, resolve_database_url

CODE=re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,39}$")
SPECS={
 "company": {"required":("company_id","standard_name"),"allowed":{}},
 "participation":{"required":("company_id","scope_type","scope_code","role_code"),"allowed":{"scope_type":{"SITE","PROJECT","PHASE"},"role_code":{"OWNER","DEVELOPER","DESIGNER","BUILDER","OPERATOR","DBO_PROVIDER","TENANT","SELLER"}}},
 "capacity":{"required":("scope_type","scope_code","capacity_type_code","raw_value","raw_unit","capacity_stage","measurement_basis"),"allowed":{"scope_type":{"SITE","PROJECT","PHASE"},"capacity_stage":{"ANNOUNCED","SECURED","DESIGNED","UNDER_CONSTRUCTION","INSTALLED","OPERATING"},"measurement_basis":{"PUBLISHED_CAPACITY","NAMEPLATE","CONTRACTED","AVAILABLE","ALLOCATED","METERED_PEAK","METERED_AVG"}}},
 "evidence":{"required":("source_code","title","document_type","source_grade"),"allowed":{"document_type":{"PERMIT","CONTRACT","DISCLOSURE","PRESS_RELEASE","NEWS","IM","WEB_PAGE","PDF","API_RESPONSE","RSS_ITEM","OTHER"},"source_grade":{"A","B","C","D"}}},
}
FIELDS={
 "company":("company_id","standard_name","legal_name","business_registration_no","official_url","note"),
 "participation":("company_id","scope_type","scope_code","role_code","valid_from","valid_to","confidence_score","evidence_url","note"),
 "capacity":("scope_type","scope_code","capacity_type_code","raw_value","raw_unit","normalized_value_mw","normalized_value","normalized_unit","capacity_stage","measurement_basis","effective_from","effective_to","document_url","evidence_location","note"),
 "evidence":("source_code","canonical_url","external_document_id","title","document_type","publisher","published_at","source_grade"),
}
DATE_FIELDS={"valid_from","valid_to","effective_from","effective_to"}
URL_FIELDS={"official_url","evidence_url","document_url","canonical_url"}

def clean(v:Any)->str:return " ".join(str(v or "").strip().split())
def validate(kind:str, names:list[str]|None, raw_rows:list[dict[str,str]]):
 errors=[]; spec=SPECS[kind]
 missing=[x for x in spec["required"] if x not in (names or [])]
 if missing:return [],[(1,x,"필수 열 누락") for x in missing]
 rows=[]; seen=set()
 for no,raw in enumerate(raw_rows,2):
  row={f:clean(raw.get(f)) for f in FIELDS[kind]}
  for f in spec["required"]:
   if not row[f]:errors.append((no,f,"필수값 누락"))
  key=tuple(row[f] for f in spec["required"])
  if key in seen:errors.append((no,"row","파일 내 중복"))
  seen.add(key)
  for f,allowed in spec["allowed"].items():
   if row[f] and row[f] not in allowed:errors.append((no,f,"허용되지 않은 값"))
  for f in DATE_FIELDS & set(row):
   try:row[f]=date.fromisoformat(row[f]) if row[f] else None
   except ValueError:errors.append((no,f,"YYYY-MM-DD 형식 필요"));row[f]=None
  for f in URL_FIELDS & set(row):
   if row[f] and urlparse(row[f]).scheme not in {"http","https"}:errors.append((no,f,"HTTP(S) URL 필요"))
  if kind=="company" and row["company_id"] and not CODE.fullmatch(row["company_id"]):errors.append((no,"company_id","코드 형식 오류"))
  if kind=="participation" and row["confidence_score"]:
   try:
    row["confidence_score"]=float(row["confidence_score"])
    if not 0<=row["confidence_score"]<=1:raise ValueError
   except ValueError:errors.append((no,"confidence_score","0~1 숫자 필요"));row["confidence_score"]=None
  if kind=="capacity":
   for f in ("normalized_value_mw","normalized_value"):
    try:row[f]=float(row[f]) if row[f] else None
    except ValueError:errors.append((no,f,"양수 숫자 필요"));row[f]=None
    if row[f] is not None and row[f]<=0:errors.append((no,f,"양수 숫자 필요"))
  if kind=="evidence" and row["published_at"]:
   try:row["published_at"]=datetime.fromisoformat(row["published_at"].replace("Z","+00:00"))
   except ValueError:errors.append((no,"published_at","ISO 날짜시간 형식 필요"));row["published_at"]=None
  rows.append(row)
 return rows,errors

def read_file(kind,path):
 with path.open(encoding="utf-8-sig",newline="") as f:
  r=csv.DictReader(f);return validate(kind,r.fieldnames,list(r))

def resolve_scope(conn,typ,code):
 table,key={"SITE":("dc_site","site_code"),"PROJECT":("dc_project","project_code"),"PHASE":("project_phase","phase_code")}[typ]
 return conn.execute(text(f"SELECT {typ.lower()}_id FROM {table} WHERE {key}=:code"),{"code":code}).scalar()

def import_rows(engine,kind,rows):
 count=0
 with engine.begin() as c:
  for r in rows:
   if kind=="company":
    q="""INSERT INTO company(company_id,standard_name,legal_name,business_registration_no,official_url,review_status,note) VALUES(:company_id,:standard_name,NULLIF(:legal_name,''),NULLIF(:business_registration_no,''),NULLIF(:official_url,''),'CANDIDATE',NULLIF(:note,'')) ON CONFLICT(company_id) DO NOTHING"""
   elif kind=="participation":
    r["scope_id"]=resolve_scope(c,r["scope_type"],r["scope_code"])
    if not r["scope_id"]:raise ValueError(f"unknown scope: {r['scope_code']}")
    q="""INSERT INTO company_participation(company_id,scope_type,scope_id,role_code,valid_from,valid_to,review_status,confidence_score,evidence_url,public_visible,note) VALUES(:company_id,:scope_type,:scope_id,:role_code,:valid_from,:valid_to,'CANDIDATE',:confidence_score,NULLIF(:evidence_url,''),false,NULLIF(:note,''))"""
   elif kind=="capacity":
    r["scope_id"]=resolve_scope(c,r["scope_type"],r["scope_code"])
    if not r["scope_id"]:raise ValueError(f"unknown scope: {r['scope_code']}")
    q="""INSERT INTO capacity_snapshot(scope_type,scope_id,capacity_type_code,raw_value,raw_unit,normalized_value_mw,normalized_value,normalized_unit,capacity_stage,measurement_basis,effective_from,effective_to,document_url,evidence_location,review_status,note) VALUES(:scope_type,:scope_id,:capacity_type_code,:raw_value,:raw_unit,:normalized_value_mw,:normalized_value,NULLIF(:normalized_unit,''),:capacity_stage,:measurement_basis,:effective_from,:effective_to,NULLIF(:document_url,''),NULLIF(:evidence_location,''),'CANDIDATE',NULLIF(:note,''))"""
   else:
    q="""INSERT INTO evidence_document(source_id,canonical_url,external_document_id,title,document_type,publisher,published_at,source_grade,access_scope) SELECT source_id,NULLIF(:canonical_url,''),NULLIF(:external_document_id,''),:title,:document_type,NULLIF(:publisher,''),:published_at,:source_grade,'INTERNAL' FROM source_registry WHERE source_code=:source_code"""
   result=c.execute(text(q),r)
   if result.rowcount!=1 and kind in {"participation","capacity","evidence"}:raise ValueError("참조 코드가 존재하지 않음")
   count+=result.rowcount
 return count

def main():
 p=argparse.ArgumentParser();p.add_argument("kind",choices=SPECS);p.add_argument("csv_file",type=Path);p.add_argument("--apply",action="store_true");a=p.parse_args()
 rows,errors=read_file(a.kind,a.csv_file)
 if errors:
  for e in errors[:50]:print(f"행 {e[0]} {e[1]}: {e[2]}",file=sys.stderr)
  return 2
 print(f"검증 성공: {len(rows)}건")
 if not a.apply:print("dry-run 완료: DB를 변경하지 않았습니다.");return 0
 load_env_file();engine=create_engine(resolve_database_url(),pool_pre_ping=True)
 try:count=import_rows(engine,a.kind,rows)
 except Exception as e:print(f"반입 실패: {type(e).__name__}",file=sys.stderr);return 1
 finally:engine.dispose()
 print(f"반입 완료: {count}건");return 0
if __name__=="__main__":raise SystemExit(main())
