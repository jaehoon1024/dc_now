#!/usr/bin/env python3
"""Reconcile a user-supplied XLSX with public permits; preserves source facts and provenance."""
import argparse,json
from pathlib import Path
from permit_intelligence import load_reference
from permit_workbook import WORKBOOK_REFERENCE,import_workbook
from src30_collect_permit_intelligence import save

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('workbook',type=Path);p.add_argument('--output',type=Path,default=WORKBOOK_REFERENCE)
    args=p.parse_args();dataset=load_reference(include_workbook=False)
    if dataset is None:raise ValueError('Missing permit baseline')
    report=import_workbook(args.workbook,dataset)
    save(args.output,report)
    print(json.dumps(report['summary'],ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
