#!/usr/bin/env python3
"""Refresh public permit facts before publishing; keeps the last good snapshot on failure."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from permit_intelligence import REFERENCE,SOURCE_URL,build,load_reference


def save(path, dataset):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(dataset,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(path)


def refresh(path=REFERENCE,input_path=None):
    previous=load_reference(path)
    try:
        if input_path:
            document=json.loads(input_path.read_text(encoding='utf-8'))
        else:
            request=Request(SOURCE_URL,headers={'User-Agent':'DC-NOW public-source review','Accept':'application/json'})
            with urlopen(request,timeout=25) as response:
                content=response.read(12000001)
                if len(content)>12000000:raise ValueError('Oversized public response')
                document=json.loads(content)
        dataset=build(document,previous)
        save(path,dataset)
        print(f"인허가 수집 성공: {len(dataset['items'])}건 / 신규 {dataset['collection']['added_records']}건 / 변경 {dataset['collection']['changed_records']}건")
        return 0
    except Exception as error:
        if previous:
            code='HTTP_'+str(error.code) if isinstance(error,HTTPError) else type(error).__name__
            previous['collection']={**previous.get('collection',{}),'status':'FAILED_KEPT_PREVIOUS','attempted_at':datetime.now(timezone.utc).isoformat(),'error_code':code}
            save(path,previous)
            print('인허가 수집 실패: 마지막 성공 자료 유지 · 공개 화면에 실패 상태 표시')
            return 0
        print('인허가 수집 실패: 발행할 정상 자료 없음')
        return 2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,help='Normalize an already acquired public JSON instead of fetching')
    parser.add_argument('--output',type=Path,default=REFERENCE)
    args=parser.parse_args()
    return refresh(args.output,args.input)


if __name__=='__main__':
    raise SystemExit(main())
