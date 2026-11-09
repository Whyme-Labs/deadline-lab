"""Native QNX runner plus an offline, independently observed effect checker.

The runner refuses non-QNX hosts. Offline checker tests use explicitly synthetic
records; they are not QNX emulation, compilation or execution evidence.
"""
from __future__ import annotations
from collections import Counter
import errno
import json
import os
import platform
import select
import subprocess
import sys
from pathlib import Path
from typing import Any
from ..evidence import digest, seal, verify
from ..trace import read_trace

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {'scenario.json', 'clients.json', 'server.jsonl', 'effects.jsonl',
            'target.json', 'completion.json', 'server.stderr', 'observer.stderr'}
DEFAULT_SCENARIO = {'schema': 2, 'adapter': 'qnx-native', 'name': 'unblock-before-effect',
    'actions': [{'op': 'call', 'work_ms': 150, 'timeout_ms': 25, 'expect_unblock': True}]}


def validate(scenario: dict[str, Any]) -> None:
    if not isinstance(scenario, dict) or scenario.get('schema') != 2 or scenario.get('adapter') != 'qnx-native':
        raise ValueError('expected schema 2 qnx-native scenario')
    actions = scenario.get('actions')
    if not isinstance(actions, list) or not 1 <= len(actions) <= 8:
        raise ValueError('native scenario requires 1..8 calls')
    for a in actions:
        if not isinstance(a, dict) or set(a) != {'op', 'work_ms', 'timeout_ms', 'expect_unblock'}:
            raise ValueError('invalid native call fields')
        if a['op'] != 'call' or type(a['work_ms']) is not int or not 0 <= a['work_ms'] <= 1000:
            raise ValueError('invalid work duration')
        if type(a['timeout_ms']) is not int or not 1 <= a['timeout_ms'] <= 5000 or type(a['expect_unblock']) is not bool:
            raise ValueError('invalid timeout or expectation')
    if not any(a['expect_unblock'] for a in actions):
        raise ValueError('at least one unblock activation must be required')


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def evaluate(out: Path) -> dict[str, Any]:
    errors: list[str] = []
    violations: list[dict[str, Any]] = []
    activations = 0
    effect_count = 0
    healthy = 0
    origin = 'unknown'
    try:
        verify(out, REQUIRED)
        scenario = json.loads((out / 'scenario.json').read_text()); validate(scenario)
        target = json.loads((out / 'target.json').read_text())
        origin = target.get('evidence_origin', 'unknown')
        if origin not in {'native-qnx', 'synthetic-unit-test'}:
            raise ValueError('unrecognised native evidence origin')
        completion = json.loads((out / 'completion.json').read_text())
        if not completion.get('complete'):
            raise ValueError('incomplete native run: ' + str(completion.get('error')))
        if completion.get('server_exit') != 0 or completion.get('observer_exit') != 0:
            raise ValueError('unclean server or observer exit')
        clients = json.loads((out / 'clients.json').read_text())
        events = [json.loads(line) for line in (out / 'server.jsonl').read_text().splitlines()]
        if not events or events[0].get('kind') != 'start' or events[-1].get('kind') != 'end':
            raise ValueError('server lifecycle log incomplete')
        times = [e['monotonic_ns'] for e in events]
        if times != sorted(times):
            raise ValueError('server event clock order')
        records = read_trace(out / 'effects.jsonl')
        effects = records[1:-1]
        effect_count = len(effects)
        if len(clients) != len(scenario['actions']) + 1:
            raise ValueError('missing native client observations or healthy probe')
        by_id = {c['id']: c for c in clients}
        if len(by_id) != len(clients) or set(by_id) != set(range(1, len(clients) + 1)):
            raise ValueError('native request IDs incomplete or duplicated')
        counts: Counter[int] = Counter()
        state = 0
        for effect in effects:
            cid = effect['command_id']
            c = by_id.get(cid)
            if c is None or effect['attempt'] != cid:
                raise ValueError('effect cannot be associated with a client request')
            if effect['request_epoch'] != c['epoch'] or effect['worker_epoch'] != c['epoch']:
                raise ValueError('native effect generation mismatch')
            if not (c['issued_ns'] <= effect['commit_ns'] <= effect['observed_ns']):
                raise ValueError('native effect timestamp mismatch')
            if effect['delta'] != 1 or effect['state_before'] != state or effect['state_after'] != state + 1:
                raise ValueError('independent virtual state mismatch')
            if effect['commit_ns'] >= c['expires_ns']:
                violations.append({'property': 'authorisation_deadline', 'id': cid})
            state += 1; counts[cid] += 1
            if counts[cid] > 1:
                violations.append({'property': 'at_most_once', 'id': cid})
        if records[-1]['final_state'] != state:
            raise ValueError('final observed state mismatch')
        logged = Counter(e['id'] for e in events if e['kind'] == 'effect')
        if logged != counts:
            raise ValueError('server effect log disagrees with independent observer')
        for cid, c in by_id.items():
            if c['status'] == 0:
                if c.get('reply_version') != 1 or c.get('reply_id') != cid:
                    raise ValueError('native reply ABI/identity mismatch')
                if c['reply_result'] == 1 and counts[cid] != 1:
                    raise ValueError('apply reply without independently observed effect')
        for cid, action in enumerate(scenario['actions'], 1):
            c = by_id[cid]
            received = [e for e in events if e['id'] == cid and e['kind'] == 'received']
            unblock = [e for e in events if e['id'] == cid and e['kind'] in {'unblock_observed', 'cancel_precommit'}]
            if action['expect_unblock']:
                if len(received) != 1 or not unblock:
                    errors.append(f'unblock fault not observed for request {cid}')
                    continue
                if min(e['monotonic_ns'] for e in unblock) < received[0]['monotonic_ns']:
                    errors.append('unblock precedes receipt')
                    continue
                activations += 1
                if counts[cid]:
                    violations.append({'property': 'cancel_before_effect', 'id': cid})
                elif c['status'] != -1 or c['errno'] not in target['timeout_errnos']:
                    errors.append('no effect but expected native cancellation result missing')
            elif counts[cid] != 1:
                violations.append({'property': 'healthy_progress', 'id': cid})
        probe = len(clients)
        healthy = counts[probe]
        if healthy != 1 or by_id[probe]['status'] != 0:
            violations.append({'property': 'healthy_progress', 'id': probe})
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        errors.append(str(exc))
    return {'verdict': 'INCONCLUSIVE' if errors else 'FAIL' if violations else 'PASS',
        'properties': sorted({v['property'] for v in violations}), 'violations': violations,
        'evidence_errors': errors, 'observed_effects': effect_count,
        'healthy_effects': healthy, 'unblock_activations': activations,
        'evidence_origin': origin,
        'qnx_executed': origin == 'native-qnx',
        'limits': 'Evidence for a cooperative virtual-effect cancellation policy. '
                  'No atomic hardware cancellation, production safety or worst-case latency claim.'}


def run(scenario: dict[str, Any], mode: str, out: Path, bin_dir: Path) -> dict[str, Any]:
    validate(scenario)
    if mode not in {'reference', 'ignore_unblock'}:
        raise ValueError('unsupported native mode')
    out.mkdir(parents=True, exist_ok=False)
    if platform.system() != 'QNX':
        result = {'verdict': 'NOT_RUN', 'qnx_executed': False,
                  'reason': 'requires a real QNX target; no emulated API substitute',
                  'host': platform.system()}
        _write(out / 'result.json', result)
        return result
    bin_dir = bin_dir.resolve()
    server_binary = bin_dir / 'dl-qnx-server'
    client_binary = bin_dir / 'dl-qnx-client'
    if not server_binary.is_file() or not client_binary.is_file():
        result = {'verdict': 'NOT_RUN', 'qnx_executed': False, 'reason': 'native binaries missing'}
        _write(out / 'result.json', result); return result
    out = out.resolve()
    _write(out / 'scenario.json', scenario)
    target = {'evidence_origin': 'native-qnx', 'os': platform.platform(), 'machine': platform.machine(),
              'timeout_errnos': [errno.ETIMEDOUT, errno.ECANCELED],
              'server_sha256': digest(server_binary), 'client_sha256': digest(client_binary),
              'policy': mode, 'observer': 'separate-process/virtual-integer-state'}
    _write(out / 'target.json', target)
    clients = []
    error = None
    server = observer = None
    read_fd, write_fd = os.pipe()
    server_err = (out / 'server.stderr').open('wb')
    observer_err = (out / 'observer.stderr').open('wb')
    try:
        observer = subprocess.Popen([sys.executable, '-S', '-m', 'deadline_lab.plant', '--fd', str(read_fd),
            '--out', str(out / 'effects.jsonl')], stdout=subprocess.PIPE, stderr=observer_err,
            pass_fds=(read_fd,), cwd=ROOT)
        os.close(read_fd); read_fd = -1
        ready, _, _ = select.select([observer.stdout], [], [], 3)
        if not ready or observer.stdout.readline() != b'READY\n':
            raise RuntimeError('independent observer did not start')
        server = subprocess.Popen([str(server_binary), mode, '1', str(out / 'server.jsonl'), str(write_fd)],
                                  stdout=subprocess.PIPE, stderr=server_err, pass_fds=(write_fd,))
        os.close(write_fd); write_fd = -1
        ready, _, _ = select.select([server.stdout], [], [], 3)
        if not ready:
            raise RuntimeError('native server startup deadline')
        endpoint = server.stdout.readline().decode('ascii').split()
        if len(endpoint) != 4 or endpoint[0] != 'READY' or int(endpoint[1]) != server.pid:
            raise RuntimeError('invalid native endpoint')
        _, pid, chid, epoch = endpoint
        calls = scenario['actions'] + [{'work_ms': 1, 'timeout_ms': 1500}]
        for cid, a in enumerate(calls, 1):
            process = subprocess.run([str(client_binary), pid, chid, epoch, str(cid),
                str(a['work_ms']), str(a['timeout_ms'])], capture_output=True, text=True,
                timeout=7, check=True)
            observation = json.loads(process.stdout)
            if observation['id'] != cid:
                raise RuntimeError('native client ID mismatch')
            clients.append(observation)
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        if server:
            if server.poll() is None:
                server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait(timeout=2)
                error = error or 'server did not stop gracefully'
            server.stdout.close()
        for fd in (read_fd, write_fd):
            if fd >= 0:
                os.close(fd)
        if observer:
            try:
                observer.wait(timeout=3)
            except subprocess.TimeoutExpired:
                observer.kill(); observer.wait(timeout=2)
                error = error or 'observer did not observe EOF'
            observer.stdout.close()
        server_err.close(); observer_err.close()
    _write(out / 'clients.json', clients)
    _write(out / 'completion.json', {'complete': error is None, 'error': error,
        'server_exit': server.returncode if server else None,
        'observer_exit': observer.returncode if observer else None})
    for name in REQUIRED:
        if not (out / name).exists():
            (out / name).write_text('')
    seal(out, sorted(REQUIRED))
    result = evaluate(out)
    result.update(mode=mode, adapter='qnx-native')
    _write(out / 'result.json', result)
    return result
