#!/usr/bin/env python3
"""Run on a licensed QNX target with Python 3. Never emulates QNX on Linux.

A timeout before server receipt is INCONCLUSIVE for the unblock test. A positive
healthy call is mandatory. The event log is canary instrumentation, not independent
physical-sensor evidence. Full workbench transport integration is a later gate.
"""
import argparse
import errno
import json
import platform
import select
import subprocess
import time
from pathlib import Path


def run_case(directory, server_binary, client_binary, mode):
    log = directory / (mode + '.jsonl')
    stderr = (directory / (mode + '.stderr')).open('w')
    server = subprocess.Popen([str(server_binary), mode, '1', str(log)],
                              stdout=subprocess.PIPE, stderr=stderr, text=True)
    result = {'mode': mode, 'verdict': 'INCONCLUSIVE', 'qnx_executed': True}
    try:
        ready, _, _ = select.select([server.stdout], [], [], 3)
        if not ready:
            raise RuntimeError('server startup timeout')
        fields = server.stdout.readline().split()
        if len(fields) != 4 or fields[0] != 'READY' or int(fields[1]) != server.pid:
            raise RuntimeError('invalid server endpoint')
        _, pid, chid, epoch = fields
        observations = []
        for cid, work, timeout in [(1, 150, 25), (2, 1, 1500)]:
            completed = subprocess.run([str(client_binary), pid, chid, epoch, str(cid), str(work), str(timeout)],
                                       capture_output=True, text=True, timeout=3, check=True)
            observations.append(json.loads(completed.stdout))
        events = [json.loads(line) for line in log.read_text().splitlines()]
        fault_observed = any(e['id'] == 1 and e['kind'] in {'unblock_observed', 'cancel_precommit'} for e in events)
        bad_effect = any(e['kind'] == 'effect' and e['id'] == 1 for e in events)
        healthy_effect = sum(e['kind'] == 'effect' and e['id'] == 2 for e in events) == 1
        expected_timeout = observations[0]['status'] == -1 and observations[0]['errno'] in {errno.ETIMEDOUT, errno.ECANCELED}
        if not fault_observed:
            verdict = 'INCONCLUSIVE'
        elif not healthy_effect:
            verdict = 'FAIL'
        elif bad_effect:
            verdict = 'FAIL'
        else:
            verdict = 'PASS' if expected_timeout else 'INCONCLUSIVE'
        result.update(verdict=verdict, observations=observations, events=events,
                      fault_observed=fault_observed, bad_effect=bad_effect, healthy_effect=healthy_effect)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        result['error'] = str(exc)
    finally:
        if server.poll() is None:
            server.kill()
        server.wait(timeout=3)
        if server.stdout:
            server.stdout.close()
        stderr.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bin', type=Path, default=Path('.'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != 'QNX':
        print(json.dumps({'verdict':'NOT_RUN','reason':'requires a real QNX target','qnx_executed':False}))
        return 77
    args.out.mkdir(parents=True, exist_ok=False)
    results = [run_case(args.out.resolve(), (args.bin/'dl-qnx-server').resolve(),
                        (args.bin/'dl-qnx-client').resolve(), mode)
               for mode in ['reference','ignore_unblock']]
    summary = {'environment': platform.platform(), 'results': results}
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return 0 if results[0]['verdict']=='PASS' and results[1]['verdict']=='FAIL' else 1

if __name__ == '__main__':
    raise SystemExit(main())
