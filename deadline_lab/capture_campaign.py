"""Retain actual POSIX collector evidence. This campaign cannot pass a QNX gate."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
from . import capture
from .adapters.qnx_native import DEFAULT_SCENARIO
from .evidence import seal
from .source_manifest import manifest


def run(bin_dir: Path, out: Path, repetitions: int = 3) -> dict:
    if type(repetitions) is not int or not 1 <= repetitions <= 5:
        raise ValueError('use 1..5 bounded transport repetitions')
    bin_dir=bin_dir.resolve()
    out.mkdir(parents=True,exist_ok=False)
    capture.write(out/'source-manifest.json',manifest(capture.ROOT,executable_only=True))
    cases=[('normal','normal',150,0,'COMPLETE'),('effect-burst','burst',150,0,'COMPLETE'),
           ('stderr-burst','stderr_burst',150,0,'COMPLETE'),
           ('partial-greeting','partial',150,78,'INCOMPLETE'),
           ('wrong-pid','wrong_pid',150,78,'INCOMPLETE'),('early-exit','crash',150,78,'INCOMPLETE'),
           ('output-limit','flood',150,78,'INCOMPLETE'),('partial-effect','partial_effect',150,78,'INCOMPLETE'),
           ('bad-effect','bad_effect',150,78,'INCOMPLETE'),('effect-size','oversize_effect',150,78,'INCOMPLETE'),
           ('effect-count','many_effects',150,78,'INCOMPLETE'),('termination-escalation','stubborn',150,78,'INCOMPLETE'),
           ('client-stall','normal',998,78,'INCOMPLETE'),('client-output-limit','normal',997,78,'INCOMPLETE'),
           ('client-exit','normal',996,78,'INCOMPLETE'),('native-refusal','reference',150,77,'NOT_RUN')]
    rows=[]
    for rep in range(repetitions):
        for name,policy,work,expected_exit,expected_status in cases:
            directory=out/f'{rep}-{name}';directory.mkdir()
            scratch=directory/'scratch';scratch.mkdir()
            scenario={**DEFAULT_SCENARIO,'actions':[dict(DEFAULT_SCENARIO['actions'][0],work_ms=work)]}
            token=secrets.token_hex(16)
            argv=capture.capture_command(str(bin_dir),policy,scenario,token,
                fixture=name!='native-refusal',budget_ms=400)
            env={**os.environ,'PATH':'/not-a-target-interpreter','TMPDIR':str(scratch.resolve())}
            obs=capture.execute(argv,timeout=5,env=env)
            (directory/'transport.stdout').write_bytes(obs.pop('stdout'))
            (directory/'transport.stderr').write_bytes(obs.pop('stderr'))
            capture.write(directory/'transport.json',obs)
            raw=capture.decode_stream((directory/'transport.stdout').read_bytes())
            for file,data in raw.items():(directory/file).write_bytes(data)
            cap=capture.loads(raw['capture.json'])
            observed_cleanup=True
            for pid in [cap['server_pid']]+[c['pid'] for c in cap['calls']]:
                if pid:
                    try:os.kill(pid,0);observed_cleanup=False
                    except ProcessLookupError:pass
            empty=not list(scratch.iterdir())
            if empty:scratch.rmdir()
            hashes_ok=True
            if 'binaries.json' in raw:
                for role,record in capture.loads(raw['binaries.json'])['binaries'].items():
                    filename='dl-capture' if role=='capture' else 'dl-transport-'+role
                    data=(bin_dir/filename).read_bytes()
                    hashes_ok=hashes_ok and record['sha256']==hashlib.sha256(data).hexdigest() and record['bytes']==len(data) and record['stable'] is True
            checked=(obs['exit']==expected_exit and cap['status']==expected_status and not cap['qnx_executed']
                     and obs['error'] is None and observed_cleanup and empty and hashes_ok and cap['token']==token)
            row={'case':name,'repetition':rep,'path':directory.name,'expected_exit':expected_exit,
                 'actual_exit':obs['exit'],'status':cap['status'],'expected_outcome_observed':checked,
                 'owned_children_gone':observed_cleanup,'scratch_removed':empty,'binary_hashes_match':hashes_ok,
                 'elapsed_seconds':obs['elapsed_seconds'],'qnx_executed':False}
            capture.write(directory/'check.json',row)
            seal(directory,sorted(p.name for p in directory.iterdir() if p.is_file()))
            rows.append(row)
    result={'schema':1,'milestone':'host-driven C capture transport','repetitions':repetitions,
            'case_families':len(cases),'executions':len(rows),
            'expectations_met':sum(r['expected_outcome_observed'] for r in rows),
            'passed':all(r['expected_outcome_observed'] for r in rows),'qnx_compiled':False,'qnx_executed':False,
            'evidence_origin':'real-posix-processes/test-fixtures','rows':rows,
            'limits':'Transport and cleanup tests only. No QNX API emulation, native cancellation observations, SSH session, or physical actuator.'}
    capture.write(out/'summary.json',result)
    return result


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bin',type=Path,default=Path('build'));p.add_argument('--out',type=Path,required=True)
    p.add_argument('--repetitions',type=int,default=3)
    a=p.parse_args();result=run(a.bin,a.out,a.repetitions)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
