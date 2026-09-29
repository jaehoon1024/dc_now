#!/usr/bin/env python3
"""Import candidate facts and link them to evidence documents."""
from __future__ import annotations
import argparse,csv,json,sys
from datetime import date
from pathlib import Path
from sqlalchemy import create_engine,text
from src04_rss_collector import load_env_file,resolve_database_url

REQ=("scope_type","scope_code","field_name","value_type","raw_value_text","claim_origin","source_grade","document_id")
ALLOWED={"scope_type":{"SITE","PROJECT","PHASE","COMPANY","CAPACITY","EVENT"},"value_type":{"TEXT","NUMBER","DATE","BOOLEAN","JSON"},"claim_origin":{"PRIMARY","REQUOTE","INFERENCE"},"source_grade":{"A","B","C","D"}}
def validate(names,raws):
 missing=[x for x in REQ if x not in(names or [])]
 if missing:return [],[(1,x,"필수 열 누락") for x in missing]
 rows=[];errors=[]
 for no,x in enumerate(raws,2):
  r={k:str(x.get(k) or '').strip() for k in REQ+("normalized_value","normalized_unit","effective_from","effective_to","confidence_score","evidence_location","quote_text")}
  for k in REQ:
   if not r[k]:errors.append((no,k,"필수값 누락"))
  for k,a in ALLOWED.items():
   if r[k] and r[k] not in a:errors.append((no,k,"허용되지 않은 값"))
  if r["normalized_value"]:
   try:r["normalized_value"]=json.loads(r["normalized_value"])
   except json.JSONDecodeError:errors.append((no,"normalized_value","JSON 형식 필요"));r["normalized_value"]=None
  else:r["normalized_value"]=None
  for k in ("effective_from","effective_to"):
   try:r[k]=date.fromisoformat(r[k]) if r[k] else None
   except ValueError:errors.append((no,k,"YYYY-MM-DD 형식 필요"));r[k]=None
  try:r["confidence_score"]=float(r["confidence_score"]) if r["confidence_score"] else None
  except ValueError:errors.append((no,"confidence_score","0~1 숫자 필요"));r["confidence_score"]=None
  if r["confidence_score"] is not None and not 0<=r["confidence_score"]<=1:errors.append((no,"confidence_score","0~1 숫자 필요"))
  rows.append(r)
 return rows,errors
def resolve_scope(c,t,code):
 if t=="COMPANY":return c.execute(text("SELECT company_id FROM company WHERE company_id=:c"),{"c":code}).scalar()
 table,key,idcol={"SITE":("dc_site","site_code","site_id"),"PROJECT":("dc_project","project_code","project_id"),"PHASE":("project_phase","phase_code","phase_id")}.get(t,(None,None,None))
 if not table:return code
 return c.execute(text(f"SELECT {idcol}::text FROM {table} WHERE {key}=:c"),{"c":code}).scalar()
def import_rows(engine,rows):
 n=0
 with engine.begin() as c:
  for r in rows:
   scope=resolve_scope(c,r["scope_type"],r["scope_code"])
   if not scope:raise ValueError("unknown scope")
   r["scope_id"]=str(scope);r["norm_json"]=json.dumps(r["normalized_value"],ensure_ascii=False) if r["normalized_value"] is not None else None
   fact=c.execute(text("""INSERT INTO extracted_fact(scope_type,scope_id,field_name,value_type,raw_value_text,normalized_value,normalized_unit,claim_origin,source_grade,effective_from,effective_to,review_status,confidence_score) VALUES(:scope_type,:scope_id,:field_name,:value_type,:raw_value_text,CAST(:norm_json AS jsonb),NULLIF(:normalized_unit,''),:claim_origin,:source_grade,:effective_from,:effective_to,'CANDIDATE',:confidence_score) RETURNING fact_id"""),r).scalar_one()
   result=c.execute(text("""INSERT INTO fact_evidence(fact_id,document_id,evidence_location,quote_text,is_primary) SELECT :fact,document_id,NULLIF(:evidence_location,''),NULLIF(:quote_text,''),true FROM evidence_document WHERE document_id=:document"""),{"fact":fact,"document":r["document_id"],**r})
   if result.rowcount!=1:raise ValueError("unknown document")
   n+=1
 return n
def main():
 p=argparse.ArgumentParser();p.add_argument("csv_file",type=Path);p.add_argument("--apply",action="store_true");a=p.parse_args()
 with a.csv_file.open(encoding="utf-8-sig",newline="") as f:rd=csv.DictReader(f);rows,errors=validate(rd.fieldnames,list(rd))
 if errors:
  for e in errors[:50]:print(f"행 {e[0]} {e[1]}: {e[2]}",file=sys.stderr)
  return 2
 print(f"검증 성공: {len(rows)}건")
 if not a.apply:print("dry-run 완료");return 0
 load_env_file();e=create_engine(resolve_database_url())
 try:print(f"반입 완료: {import_rows(e,rows)}건")
 finally:e.dispose()
 return 0
if __name__=="__main__":raise SystemExit(main())
