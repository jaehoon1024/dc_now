"""Collect allowlisted official page metadata; never stores page bodies or confirms facts."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from urllib.robotparser import RobotFileParser

from namepf_normalize import public_url

ROOT=Path(__file__).resolve().parent
CATALOG=ROOT/'data/reference/official_collection_catalog.json'
REPORT=ROOT/'data/reference/official_collection_latest.json'
USER_AGENT='DC-NOW-Metadata/1.0'
KEYWORD=re.compile(r'데이터\s*센터|data\s*cent(?:er|re)|\bIDC\b|colocation',re.I)

class CollectionIssue(Exception):
    pass

class SameHost(HTTPRedirectHandler):
    def __init__(self,approved_redirects=()):
        self.approved_redirects=set(approved_redirects)
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        old=urlparse(req.full_url).hostname or ''
        new=urlparse(newurl).hostname or ''
        if not public_url(newurl) or urlparse(newurl).scheme!='https' or (new.removeprefix('www.')!=old.removeprefix('www.') and newurl not in self.approved_redirects):
            raise CollectionIssue('REDIRECT_REVIEW_REQUIRED')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def download(url,approved_redirects=()):
    if not public_url(url) or urlparse(url).scheme!='https':
        raise CollectionIssue('UNSAFE_URL')
    request=Request(url,headers={'User-Agent':USER_AGENT,'Accept':'text/html,text/plain'})
    with build_opener(SameHost(approved_redirects)).open(request,timeout=8) as response:
        payload=response.read(2_000_001)
        if len(payload)>2_000_000:raise CollectionIssue('RESPONSE_TOO_LARGE')
        return payload.decode(response.headers.get_content_charset() or 'utf-8',errors='replace'),response.headers.get_content_type()

class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title=[];self.title_depth=False;self.hidden=0;self.words=[];self.metadata={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in {'script','style','noscript'}:self.hidden+=1
        if tag=='title':self.title_depth=True
        if tag=='meta':self.metadata[a.get('property') or a.get('name')]=a.get('content','')
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript'}:self.hidden=max(0,self.hidden-1)
        if tag=='title':self.title_depth=False
    def handle_data(self,value):
        if self.title_depth:self.title.append(value)
        if not self.hidden:self.words.append(value)


def metadata(payload,url):
    parser=MetadataParser();parser.feed(payload)
    text=' '.join(parser.words)
    title=' '.join((parser.metadata.get('og:title') or ' '.join(parser.title)).split())[:300]
    if not title or not KEYWORD.search(text):raise CollectionIssue('NO_RELEVANT_CONTENT')
    return {'title':title,'canonical_url':url,'published_at':None,'guid':url}


def check_source(config,fetch=download,sleep=time.sleep):
    robots=urljoin(config['url'],'/robots.txt');delay=0
    try:
        reviewed=config.get('reviewed_robots_redirect')
        rules,mime=download(robots,(reviewed,)) if fetch is download and reviewed else fetch(robots)
        if '<html' in rules[:1000].lower() or mime not in {'text/plain','text/x-robots-txt'}:
            if not (reviewed and config.get('robots_reviewed_absent')):
                raise CollectionIssue('ROBOTS_REVIEW_REQUIRED')
            robots_status='REVIEWED_NO_RULES'
        else:
            parser=RobotFileParser();parser.parse(rules.splitlines())
            if not parser.can_fetch(USER_AGENT,config['url']):raise CollectionIssue('ROBOTS_DISALLOWED')
            delay=parser.crawl_delay(USER_AGENT) or 0
            if delay>30:raise CollectionIssue('CRAWL_DELAY_REVIEW_REQUIRED')
            robots_status='ALLOWED'
    except HTTPError as error:
        if error.code not in {404,410}:raise
        robots_status='ABSENT'
    interval=max(int(config.get('request_interval_seconds') or 0),delay)
    if interval:sleep(interval)
    body,mime=fetch(config['url'])
    if mime!='text/html':raise CollectionIssue('UNEXPECTED_CONTENT_TYPE')
    item=metadata(body,config['url'])
    return item,robots_status


def collect(engine,configs=None,fetch=download):
    from sqlalchemy import text
    from src04_rss_collector import store_items
    from src27_apply_source_review import audit
    from src30_collect_permit_intelligence import save
    configs=configs if configs is not None else json.loads(CATALOG.read_text())['sources']
    checked=datetime.now(timezone.utc).isoformat()
    previous=json.loads(REPORT.read_text()) if REPORT.exists() else {}
    old={x['source_code']:x for x in previous.get('sources',[])}
    results=[]
    with engine.begin() as c:
        run=c.execute(text("""INSERT INTO collection_run(job_name,trigger_type,requested_by,started_at,run_status,total_source_count,application_version)
          VALUES('OFFICIAL_REFERENCE_DAILY','SCHEDULED','official-metadata',CURRENT_TIMESTAMP,'RUNNING',:total,'official-metadata-1') RETURNING collection_run_id"""),{'total':len(configs)}).scalar_one()
    for config in configs:
        row={'source_code':config['source_code'],'url':config['url'],'attempted_at':datetime.now(timezone.utc).isoformat(),'status':'FAILED','new_documents':0,'last_success_at':old.get(config['source_code'],{}).get('last_success_at')}
        try:
            with engine.connect() as c:
                source=c.execute(text("""SELECT source_id,source_code,source_name,default_source_grade,source_type,collection_policy,content_storage_policy,collection_method,active,request_interval_seconds
                  FROM source_registry WHERE source_code=:source_code"""),config).mappings().first()
            if not source or source['source_type']!='COMPANY':raise CollectionIssue('SOURCE_REVIEW_REQUIRED')
            if source['collection_policy'] in {'BLOCKED','OFFICIAL_API'}:raise CollectionIssue('POLICY_REVIEW_REQUIRED')
            item,robots_status=check_source({**config,'request_interval_seconds':source['request_interval_seconds']},fetch)
            with engine.begin() as c:
                # A reviewed allowlist plus a successful policy check establishes this metadata-only route.
                after={'collection_method':'HTML','collection_policy':'METADATA_ONLY','content_storage_policy':'METADATA_ONLY','active':True}
                before={k:source[k] for k in after}
                if before!=after:
                    c.execute(text("""UPDATE source_registry SET collection_method='HTML',collection_policy='METADATA_ONLY',content_storage_policy='METADATA_ONLY',
                      active=true,terms_review_status='LIMITED',robots_review_status=:robots,compliance_checked_on=CURRENT_DATE WHERE source_id=:source_id"""),{'source_id':source['source_id'],'robots':'ALLOWED' if robots_status=='ALLOWED' else 'NOT_APPLICABLE'})
                    audit(c,'source-collection-improvement','SOURCE',source['source_id'],before,after,'사용자 승인: 공식 안내 URL 제목·링크만 수집; robots '+robots_status)
                existing=c.execute(text("SELECT document_id,external_document_id,title FROM evidence_document WHERE source_id=:source_id AND canonical_url=:url AND record_status='ACTIVE' LIMIT 1"),{'source_id':source['source_id'],'url':item['canonical_url']}).mappings().first()
            if not existing or str(existing['external_document_id']).startswith('official:'):
                feed={**dict(source),'filter_mode':'ALL','filter_keywords':[]}
                counts=store_items(engine,feed,[item],ROOT/'data/raw',collection_kind='official',collector_version='official-metadata-1',parser_name='official-page-metadata',external_id_prefix='official',document_type='WEB_PAGE')
                row['new_documents']=counts.new
            row.update(status='SUCCESS',last_success_at=datetime.now(timezone.utc).isoformat(),robots_status=robots_status,document_title=item['title'],document_count=1)
        except HTTPError as error:row['error_code']='HTTP_'+str(error.code)
        except CollectionIssue as error:row['error_code']=str(error)
        except URLError as error:row['error_code']='TLS_CERTIFICATE_ERROR' if isinstance(error.reason,ssl.SSLCertVerificationError) else 'CONNECTION_ERROR'
        except Exception as error:row['error_code']=type(error).__name__
        results.append(row)
    successes=sum(r['status']=='SUCCESS' for r in results);new=sum(r['new_documents'] for r in results)
    status='SUCCESS' if successes==len(results) else 'PARTIAL' if successes else 'FAILED'
    with engine.begin() as c:
        c.execute(text("""UPDATE collection_run SET finished_at=CURRENT_TIMESTAMP,run_status=:status,success_source_count=:success,
          failed_source_count=:failed,new_document_count=:new,error_summary=:errors WHERE collection_run_id=:run"""),{'status':status,'success':successes,'failed':len(results)-successes,'new':new,'errors':json.dumps([{'source_code':r['source_code'],'error_code':r.get('error_code')} for r in results if r['status']!='SUCCESS']),'run':run})
    report={'format':'official-collection-v1','checked_at':datetime.now(timezone.utc).isoformat(),'started_at':checked,'status':status,'summary':{'sources':len(results),'success':successes,'failed':len(results)-successes,'new_documents':new},'sources':results}
    save(REPORT,report)
    return report
