#!/usr/bin/env python3
import argparse,hashlib,importlib.util,json,os,select,sys,tempfile,threading,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from deadline_lab.reducer import reduce_actions
from deadline_lab.bounded_io import LineReader
from deadline_lab.adapters import qnx_native
from test_native_evidence import fixture
from deadline_lab.evidence import seal
parser=argparse.ArgumentParser(description='Reproduce three v0.2 workbench defects without QNX.')
parser.add_argument('--prior-archive',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
a=parser.parse_args(); E=a.out; E.mkdir(parents=True,exist_ok=False);cases=[]
BASE=hashlib.sha256(a.prior_archive.read_bytes()).hexdigest()
if BASE!='e7828f3b0e9af103e0ad90787f2004477f54556a38b82c58aef2317df7d635f0':
 raise ValueError('not the reviewed v0.2.0 archive')
with tempfile.TemporaryDirectory() as temp:
 def old_module(path,name):
  p=Path(temp)/Path(path).name
  with zipfile.ZipFile(a.prior_archive) as archive: p.write_bytes(archive.read('deadline-lab/'+path))
  spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
 old=old_module('deadline_lab/reducer.py','prior_reducer')
 def validate(s):
  if not s['actions']:raise ValueError('empty')
 def runner(s,out):
  return {'verdict':'FAIL','properties':['p']} if len(s['actions'])==2 else {'verdict':'INCONCLUSIVE','properties':[]}
 s={'actions':[{'op':'a'},{'op':'b'}]}
 _,before=old.reduce_actions(s,runner,validate,'p')
 _,after=reduce_actions(s,runner,validate,'p')
 cases.append({'name':'inconclusive_deletion_minimality','evidence_kind':'synthetic-outcome contract reproduction',
               'before':before,'after':after,'regression_fixed':before['deletion_1_minimal'] is True and after['deletion_1_minimal'] is None})
 old_q=old_module('deadline_lab/adapters/qnx_native.py','deadline_lab.adapters.prior_qnx_native')
 p=fixture(E/'post-commit-unblock-fixture',broken=True)
 events=[json.loads(x) for x in (p/'server.jsonl').read_text().splitlines()]
 for e in events:
  if e['kind']=='unblock_observed':e['monotonic_ns']=180
 events.sort(key=lambda e:e['monotonic_ns'])
 (p/'server.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events));seal(p,sorted(qnx_native.REQUIRED))
 before=old_q.evaluate(p);after=qnx_native.evaluate(p)
 (p/'prior-verdict.json').write_text(json.dumps(before,indent=2)+'\n');(p/'current-verdict.json').write_text(json.dumps(after,indent=2)+'\n')
 cases.append({'name':'unblock_after_commit','evidence_kind':'synthetic native-checker evidence, not QNX execution',
               'before':before,'after':after,'regression_fixed':before['verdict']=='FAIL' and after['verdict']=='INCONCLUSIVE'})
 r,w=os.pipe();stream=os.fdopen(r,'rb');result={}
 def prior_read():
  ready,_,_=select.select([stream],[],[],.05)
  result['value']=stream.readline().decode() if ready else None
 os.write(w,b'READY');thread=threading.Thread(target=prior_read);thread.start();thread.join(.15)
 remained_blocked=thread.is_alive()
 # Release the demonstration deliberately; no hung thread is left behind.
 os.write(w,b'\n');thread.join(2);stream.close();os.close(w)
 r,w=os.pipe();os.write(w,b'READY');start=time.monotonic();got=LineReader(r).read(.05);elapsed=time.monotonic()-start
 os.close(r);os.close(w)
 cases.append({'name':'partial_readiness_line','evidence_kind':'actual local OS pipes',
   'prior_read_still_blocked_after_150ms':remained_blocked,'current_return':got,'current_elapsed_seconds':elapsed,
   'all_resources_closed':not thread.is_alive(),'regression_fixed':remained_blocked and got is None and elapsed<1})
summary={'baseline_archive_sha256':BASE,'cases':cases,'all_fixed':all(x['regression_fixed'] for x in cases),
         'qnx_executed':False,'limits':'These are regressions in our workbench, not discovered external or QNX vulnerabilities.'}
(E/'defect-reproductions.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
