#!/usr/bin/env python3
"""Reduce a real native failure. Nothing runs on Linux, and incomplete runs fail closed."""
import argparse
import json
import platform
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deadline_lab.adapters.qnx_native import run, validate
from deadline_lab.reducer import reduce_actions


def main():
    p=argparse.ArgumentParser()
    p.add_argument('scenario',type=Path)
    p.add_argument('--bin',type=Path,default=Path('build-qnx'))
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if platform.system()!='QNX':
        print(json.dumps({'verdict':'NOT_RUN','reason':'requires actual QNX target','qnx_executed':False}))
        return 77
    source=json.loads(a.scenario.read_text());validate(source)
    witness,record=reduce_actions(source,lambda s,d:run(s,'ignore_unblock',d,a.bin),
                                  validate,'cancel_before_effect',repetitions=2,max_executions=200)
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'witness.json').write_text(json.dumps(witness,indent=2)+'\n')
    checks=[]
    for i in range(5):
        for mode in ('reference','ignore_unblock'):
            checks.append(run(witness,mode,a.out/f'{i}-{mode}',a.bin))
    ok=all(r['verdict']==('PASS' if r.get('mode')=='reference' else 'FAIL') and
           (r.get('mode')!='ignore_unblock' or 'cancel_before_effect' in r.get('properties',[])) for r in checks)
    ok = ok and record['deletion_1_minimal'] is True and record['final_reproduces']
    summary={'reduction':record,'checks':checks,'expected_outcomes_observed':ok,
             'qnx_executed':True}
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
