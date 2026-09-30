#!/usr/bin/env python3
"""Review queues and audited approval/rejection for candidate records."""
from __future__ import annotations
import argparse, json, os, sys
from dataclasses import dataclass
from typing import Any
from sqlalchemy import create_engine, text
from src04_rss_collector import load_env_file, resolve_database_url

@dataclass(frozen=True)
class Entity:
 table:str; id_column:str; label_column:str; public_column:str|None=None; reviewer_columns:bool=False; detail_columns:tuple[str,...]=()

ENTITIES={
 "site":Entity("dc_site","site_id","site_code","public_visible",False,("site_name","address_standard","sido","sigungu","location_precision","coordinate_quality")),
 "project":Entity("dc_project","project_id","project_code","public_visible",False,("project_name","project_type","status_code","planned_rfs_date","rfs_date")),
 "company":Entity("company","company_id","standard_name",None,False,("legal_name","official_url")),
 "participation":Entity("company_participation","participation_id","role_code","public_visible",False,("company_id","scope_type","confidence_score","evidence_url")),
 "capacity":Entity("capacity_snapshot","capacity_id","capacity_type_code",None,False,("scope_type","raw_value","raw_unit","normalized_value_mw","capacity_stage","measurement_basis","document_url")),
 "evidence":Entity("evidence_document","document_id","title",None,True,("document_type","publisher","published_at","source_grade","access_scope","canonical_url")),
 "fact":Entity("extracted_fact","fact_id","field_name",None,True,("scope_type","raw_value_text","normalized_value","source_grade","confidence_score")),
}

def queue(engine,kind:str|None=None,limit:int=100):
 kinds=[kind] if kind else list(ENTITIES)
 result={}
 with engine.connect() as c:
  for name in kinds:
   e=ENTITIES[name]
   details=(","+",".join(e.detail_columns)) if e.detail_columns else ""
   rows=c.execute(text(f"SELECT {e.id_column}::text AS id,{e.label_column} AS label,review_status,created_at{details} FROM {e.table} WHERE review_status IN ('CANDIDATE','NEEDS_EVIDENCE','CONFLICT') ORDER BY created_at LIMIT :limit"),{"limit":limit}).mappings()
   result[name]=[{**dict(x),"can_publish":bool(e.public_column)} for x in rows]
 return result

def review(engine,kind,record_id,decision,reviewer,note,publish=False):
 if kind not in ENTITIES or decision not in {"approve","reject"}:raise ValueError("invalid review request")
 reviewer=str(reviewer).strip();note=str(note).strip()
 if not reviewer or not note:raise ValueError("reviewer and note are required")
 e=ENTITIES[kind]; status="CONFIRMED" if decision=="approve" else "REJECTED"
 with engine.begin() as c:
  before=c.execute(text(f"SELECT {e.id_column}::text AS id,review_status FROM {e.table} WHERE {e.id_column}=:id FOR UPDATE"),{"id":record_id}).mappings().first()
  if not before:raise ValueError("record not found")
  sets=["review_status=:status","updated_at=CURRENT_TIMESTAMP"]
  params={"id":record_id,"status":status}
  if e.public_column:
   sets.append(f"{e.public_column}=:publish");params["publish"]=bool(publish and decision=="approve")
  if e.reviewer_columns:
   sets += ["reviewed_by=:reviewer","reviewed_at=CURRENT_TIMESTAMP","review_note=:note"]
   params.update(reviewer=reviewer,note=note)
  if kind=="fact" and decision=="reject":
   sets.append("rejection_reason=:note");params["note"]=note
  c.execute(text(f"UPDATE {e.table} SET {','.join(sets)} WHERE {e.id_column}=:id"),params)
  after={"id":record_id,"review_status":status,"public_visible":params.get("publish")}
  c.execute(text("""INSERT INTO audit_log(actor_id,role_at_action,action,entity_type,entity_id,before_value,after_value,reason,result) VALUES(:actor,'REVIEWER',:action,:etype,:eid,CAST(:before AS jsonb),CAST(:after AS jsonb),:reason,'SUCCESS')"""),{"actor":reviewer[:150],"action":f"REVIEW_{decision.upper()}","etype":kind.upper(),"eid":record_id,"before":json.dumps(dict(before)),"after":json.dumps(after),"reason":note})
 return after

def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True)
 q=sub.add_parser("queue");q.add_argument("--kind",choices=ENTITIES);q.add_argument("--limit",type=int,default=100);q.add_argument("--json",action="store_true")
 r=sub.add_parser("review");r.add_argument("kind",choices=ENTITIES);r.add_argument("record_id");r.add_argument("decision",choices=("approve","reject"));r.add_argument("--reviewer",default=os.getenv("USER","reviewer"));r.add_argument("--note",required=True);r.add_argument("--publish",action="store_true")
 a=p.parse_args();load_env_file();engine=create_engine(resolve_database_url(),pool_pre_ping=True)
 try:
  if a.command=="queue":print(json.dumps(queue(engine,a.kind,a.limit),default=str,ensure_ascii=False,indent=2));return 0
  print(json.dumps(review(engine,a.kind,a.record_id,a.decision,a.reviewer,a.note,a.publish),ensure_ascii=False));return 0
 except Exception as e:print(f"검토 처리 실패: {type(e).__name__}",file=sys.stderr);return 1
 finally:engine.dispose()
if __name__=="__main__":raise SystemExit(main())
