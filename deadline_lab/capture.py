"""Host-driven C capture. Python stays on the development host, never the target.

The transport is a bounded, allow-listed file stream. It is not a shell protocol,
remote attestation, or QNX emulation. POSIX process-I/O fixtures never earn native
acceptance. Raw observations remain beside deterministic derived evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import selectors
import shlex
import signal
import subprocess
import time
from typing import Any

from .evidence import seal, verify
from .source_manifest import manifest as source_manifest
from .trace import TraceWriter, read_trace

ROOT = Path(__file__).resolve().parents[1]
MAX_STREAM = 3_000_000
MAX_FILE = 65_536
FIXED_NAMES = {'capture.json', 'binaries.json', 'build-record.json', 'source-manifest.json',
               'abi.stdout', 'abi.stderr', 'server.stdout', 'server.stderr', 'server.jsonl',
               'effects.raw.jsonl'}
FRAME_NAME = re.compile(r'client-[1-9]\.(stdout|stderr)\Z')


def loads(raw: str | bytes) -> Any:
    def obj(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value: str) -> None:
        raise ValueError('non-finite JSON constant: ' + value)
    return json.loads(raw, object_pairs_hook=obj, parse_constant=constant)


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def decode_stream(data: bytes) -> dict[str, bytes]:
    """Parse entirely before writing. No archive paths, links, or unknown files."""
    if len(data) > MAX_STREAM or not data.startswith(b'DLCAP1\n'):
        raise ValueError('capture stream size or magic invalid')
    files: dict[str, bytes] = {}
    pos = 7
    while pos < len(data):
        end = data.find(b'\n', pos, pos + 128)
        if end < 0:
            raise ValueError('truncated or oversized frame header')
        line = data[pos:end]
        pos = end + 1
        if line == b'END':
            if pos != len(data) or 'capture.json' not in files:
                raise ValueError('trailing bytes or missing capture record')
            return files
        match = re.fullmatch(rb'FILE ([a-zA-Z0-9_.-]+) (0|[1-9][0-9]{0,5})', line)
        if not match:
            raise ValueError('invalid capture frame header')
        name, size = match[1].decode('ascii'), int(match[2])
        if name not in FIXED_NAMES and not FRAME_NAME.fullmatch(name):
            raise ValueError('unrecognised capture artifact')
        if name in files or len(files) >= 40 or size > MAX_FILE:
            raise ValueError('duplicate or oversized capture artifact')
        if pos + size >= len(data) or data[pos + size:pos + size + 1] != b'\n':
            raise ValueError('truncated capture artifact')
        files[name] = data[pos:pos + size]
        pos += size + 1
    raise ValueError('missing capture stream completion')


def capture_command(bin_dir: str, mode: str, scenario: dict, token: str, *,
                    ssh: str | None = None, fixture: bool = False,
                    budget_ms: int = 60000) -> list[str]:
    from .adapters.qnx_native import validate
    validate(scenario)
    if not isinstance(bin_dir, str) or not bin_dir.startswith('/') or '\x00' in bin_dir or '\n' in bin_dir:
        raise ValueError('target binary directory must be an absolute single-line POSIX path')
    if not re.fullmatch('[a-f0-9]{32}', token):
        raise ValueError('invalid capture token')
    if type(budget_ms) is not int or not 200 <= budget_ms <= 60000:
        raise ValueError('capture budget outside permitted range')
    if mode not in {'reference', 'ignore_unblock'} and not fixture:
        raise ValueError('invalid native policy')
    if fixture and (ssh is not None or not re.fullmatch('[a-z_]{1,40}', mode)):
        raise ValueError('transport fixtures are local tests only')
    calls = ','.join(f'{a["work_ms"]}:{a["timeout_ms"]}' for a in scenario['actions'])
    argv = [str(PurePosixPath(bin_dir) / 'dl-capture'), '--bin', bin_dir, '--mode', mode,
            '--calls', calls, '--token', token, '--stream', '--budget-ms', str(budget_ms)]
    if fixture:
        argv.append('--transport-fixture')
    if ssh is None:
        return argv
    # A host alias or user@host. No command-line options in the destination field.
    if not re.fullmatch(r'(?:[A-Za-z0-9_][A-Za-z0-9_.-]*@)?[A-Za-z0-9_][A-Za-z0-9_.-]*', ssh):
        raise ValueError('use a simple SSH config alias or user@hostname')
    return ['ssh', '-T', '-oBatchMode=yes', '-oStrictHostKeyChecking=yes',
            '-oConnectTimeout=5', '-oServerAliveInterval=5', '-oServerAliveCountMax=2',
            '--', ssh, shlex.join(argv)]


def execute(argv: list[str], *, timeout: float = 80, env: dict | None = None) -> dict:
    """Bound both output channels and elapsed time; reap the owned launcher.

    An SSH transport disconnect cannot prove that a remote process was reaped.
    The target collector has its own bounded run; the host does not claim remote
    cleanup on the basis of terminating the local SSH process.
    """
    if timeout <= 0 or timeout > 120:
        raise ValueError('invalid launcher timeout')
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True, env=env)
    sel = selectors.DefaultSelector()
    channels = {'stdout': bytearray(), 'stderr': bytearray()}
    error = None
    started = time.monotonic()
    deadline = started + timeout
    try:
        for key, pipe in [('stdout', process.stdout), ('stderr', process.stderr)]:
            os.set_blocking(pipe.fileno(), False)
            sel.register(pipe, selectors.EVENT_READ, key)
        while sel.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('launcher deadline expired')
            for ready, _ in sel.select(min(remaining, 0.05)):
                data = os.read(ready.fd, 16384)
                if not data:
                    sel.unregister(ready.fileobj)
                    continue
                buffer = channels[ready.data]
                limit = MAX_STREAM if ready.data == 'stdout' else MAX_FILE
                if len(buffer) + len(data) > limit:
                    raise ValueError('launcher output exceeds bound')
                buffer.extend(data)
        process.wait(timeout=max(0.05, deadline - time.monotonic()))
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        sel.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        process.stdout.close()
        process.stderr.close()
    return {'exit': process.returncode, 'error': error,
            'elapsed_seconds': time.monotonic() - started,
            'stdout': bytes(channels['stdout']), 'stderr': bytes(channels['stderr']),
            'launcher_reaped': process.poll() is not None}


def normalized_effects(raw: bytes) -> list[dict]:
    if len(raw) > MAX_FILE or not raw.endswith(b'\n'):
        raise ValueError('raw observer stream incomplete')
    rows = [loads(line) for line in raw.splitlines()]
    if len(rows) < 2 or rows[0].get('kind') != 'start' or rows[-1].get('kind') != 'end':
        raise ValueError('raw observer lifecycle missing')
    if rows[-1].get('complete') is not True or rows[-1].get('effect_count') != len(rows) - 2:
        raise ValueError('raw observer completion invalid')
    start, end = rows[0]['monotonic_ns'], rows[-1]['monotonic_ns']
    if type(start) is not int or type(end) is not int or not 0 < start <= end:
        raise ValueError('raw observer clock invalid')
    result = [{'kind': 'start', 'plant': 'virtual-integer/c-capture',
               'pid': rows[0]['pid'], 'monotonic_ns': start}]
    state, previous = 0, start
    for row in rows[1:-1]:
        if row.get('kind') != 'effect' or set(row) != {'kind', 'observed_ns', 'wire'}:
            raise ValueError('raw observer event invalid')
        stamp = row['observed_ns']
        if type(stamp) is not int or not previous <= stamp <= end:
            raise ValueError('raw observer timestamps out of order')
        wire = row['wire']
        if not isinstance(wire, str) or len(wire) > 256:
            raise ValueError('raw effect wire invalid')
        match = re.fullmatch(r'E ([1-9][0-9]{0,19}) ([1-9][0-9]{0,19}) ([1-9][0-9]{0,19}) '
                             r'([1-9][0-9]{0,19}) ([1-9][0-9]{0,19}) (-?[1-9][0-9]{0,6})\n', wire)
        if not match:
            raise ValueError('raw effect wire grammar invalid')
        cid, req, epoch, attempt, commit, delta = map(int, match.groups())
        if any(v > 2**64 - 1 for v in (cid, req, epoch, attempt, commit)) or abs(delta) > 1_000_000:
            raise ValueError('raw effect integer outside range')
        if not start <= commit <= stamp:
            raise ValueError('effect not in target monotonic observation interval')
        result.append({'kind': 'effect', 'command_id': cid, 'request_epoch': req,
                       'worker_epoch': epoch, 'attempt': attempt, 'commit_ns': commit,
                       'observed_ns': stamp, 'delta': delta, 'state_before': state,
                       'state_after': state + delta})
        state += delta
        previous = stamp
    result.append({'kind': 'end', 'complete': True, 'error': None,
                   'effect_count': len(rows) - 2, 'final_state': state, 'monotonic_ns': end})
    return result


def native_material(files: dict[str, bytes], invocation: dict) -> dict:
    """Derive canonical existing-adapter evidence from a completed native capture."""
    from .adapters.qnx_native import validate
    scenario = invocation['scenario']
    validate(scenario)
    cap = loads(files['capture.json'])
    if (cap.get('schema') != 1 or cap.get('status') != 'COMPLETE' or cap.get('error') is not None
            or cap.get('evidence_origin') != 'native-qnx' or cap.get('system') != 'QNX'
            or cap.get('qnx_executed') is not True or cap.get('interrupted') != 0):
        raise ValueError('completed genuine native capture required')
    if cap.get('token') != invocation['token'] or cap.get('policy') != invocation['mode']:
        raise ValueError('capture request identity mismatch')
    if (cap.get('server_reaped') is not True or cap.get('current_reaped') is not True
            or cap.get('server_exit') != 0 or cap.get('observer_exit') != 0):
        raise ValueError('native children did not complete cleanly')
    expected_calls = scenario['actions'] + [{'work_ms': 1, 'timeout_ms': 1500}]
    calls = cap.get('calls')
    if not isinstance(calls, list) or len(calls) != len(expected_calls):
        raise ValueError('capture call count mismatch')
    clients = []
    for i, (a, observed) in enumerate(zip(expected_calls, calls), 1):
        if (observed.get('id') != i or observed.get('work_ms') != a['work_ms']
                or observed.get('timeout_ms') != a['timeout_ms'] or observed.get('attempted') is not True
                or observed.get('exit') != 0 or type(observed.get('pid')) is not int or observed['pid'] <= 0):
            raise ValueError('capture call parameters or exit mismatch')
        if files[f'client-{i}.stderr']:
            raise ValueError('native client emitted diagnostics')
        obs = loads(files[f'client-{i}.stdout'])
        if obs.get('id') != i:
            raise ValueError('client request ID mismatch')
        clients.append(obs)
    if files['abi.stderr'] or files['server.stderr']:
        raise ValueError('native ABI/server emitted diagnostics')
    abi = loads(files['abi.stdout'])
    if abi.get('system') != 'QNX' or abi.get('schema') != 1 or abi.get('dl_schema') != 1:
        raise ValueError('QNX runtime ABI missing')
    build = loads(files['build-record.json'])
    source = loads(files['source-manifest.json'])
    identities = loads(files['binaries.json'])
    if (build.get('status') != 'COMPILED' or build.get('qnx_compiled') is not True
            or source.get('source_set_sha256') != build.get('source_set_sha256')
            or source.get('source_set_sha256') != invocation.get('expected_source_set_sha256')):
        raise ValueError('compiled source identity mismatch')
    canonical = json.dumps(source['files'], sort_keys=True, separators=(',', ':')).encode()
    if hashlib.sha256(canonical).hexdigest() != source['source_set_sha256']:
        raise ValueError('compiled source set digest mismatch')
    for role in ('server', 'client', 'abi', 'capture'):
        name = 'dl-capture' if role == 'capture' else 'dl-qnx-' + role
        identity = identities['binaries'][role]
        if (identity.get('stable') is not True or identity.get('sha256') != build['binaries'][name]['sha256']
                or identity.get('bytes') != build['binaries'][name]['bytes']):
            raise ValueError('runtime binary disagrees with compiled build: ' + role)
    target = {'evidence_origin': 'native-qnx', 'system': 'QNX', 'machine': cap['machine'],
              'os': 'QNX ' + cap['release'], 'source_set_sha256': source['source_set_sha256'],
              'policy': cap['policy'], 'timeout_errnos': cap['timeout_errnos'],
              'observer': 'separate-process/c-collector/virtual-integer-state',
              'collector': 'c-capture-v1', 'capture_token': cap['token']}
    for role in ('server', 'client', 'abi', 'capture'):
        target[role + '_sha256'] = identities['binaries'][role]['sha256']
    return {'scenario.json': scenario, 'clients.json': clients, 'abi.json': abi,
            'target.json': target, 'completion.json': {'complete': True, 'error': None,
            'server_exit': 0, 'observer_exit': 0},
            'effects': normalized_effects(files['effects.raw.jsonl'])}


def verify_imported(out: Path) -> None:
    """Called by the ordinary native checker, also during historical rechecks."""
    required = {'transport.stdout', 'transport.stderr', 'transport.json', 'invocation.json'}
    invocation = loads((out / 'invocation.json').read_bytes())
    offline = invocation.get('transport') == 'offline-file'
    if offline:
        required |= {'offline-request.json', 'capture.exit'}
    verify(out, required)
    transport = loads((out / 'transport.json').read_bytes())
    if transport.get('exit') != 0 or transport.get('error') is not None:
        raise ValueError('capture transport did not complete')
    if offline:
        from .offline import verify_offline_import
        verify_offline_import(out, invocation, transport)
    elif transport.get('launcher_reaped') is not True:
        raise ValueError('capture launcher was not reaped')
    if (out / 'transport.stderr').read_bytes():
        raise ValueError('capture transport emitted diagnostics')
    files = decode_stream((out / 'transport.stdout').read_bytes())
    verify(out, required | set(files))
    for name, data in files.items():
        if (out / name).read_bytes() != data:
            raise ValueError('raw artifact differs from captured stream')
    material = native_material(files, loads((out / 'invocation.json').read_bytes()))
    for name, value in material.items():
        if name == 'effects':
            actual = [{k: v for k, v in e.items() if k not in {'seq', 'prev', 'hash', 'schema'}}
                      for e in read_trace(out / 'effects.jsonl')]
            if actual != value:
                raise ValueError('normalized effects differ from raw target observations')
        elif loads((out / name).read_bytes()) != value:
            raise ValueError('normalized artifact differs from raw target observations: ' + name)


def materialize_native(out: Path, files: dict[str, bytes], invocation: dict) -> None:
    """Canonical import shared by live and offline transports, never a verdict."""
    material = native_material(files, invocation)
    for name, value in material.items():
        if name == 'effects':
            trace = TraceWriter(out / 'effects.jsonl')
            try:
                for row in value:
                    trace.write(**row)
            finally:
                trace.close()
        else:
            write(out / name, value)
    (out / 'observer.stderr').write_bytes(b'')
    seal(out, sorted(p.name for p in out.iterdir() if p.is_file()))


def run_native(scenario: dict, mode: str, out: Path, bin_dir: str, *, ssh: str | None = None) -> dict:
    """Run on a local QNX target or an existing authorised SSH target.

    No provisioning, transfers, licences, target policy changes or remote installs.
    """
    token = secrets.token_hex(16)
    command = capture_command(bin_dir, mode, scenario, token, ssh=ssh)
    out.mkdir(parents=True, exist_ok=False)
    invocation = {'schema': 1, 'token': token, 'mode': mode, 'scenario': scenario,
                  'expected_source_set_sha256': source_manifest(ROOT, executable_only=True)['source_set_sha256'],
                  'transport': 'ssh' if ssh else 'local-process'}
    write(out / 'invocation.json', invocation)
    result = {'verdict': 'INCONCLUSIVE', 'qnx_executed': False, 'properties': [],
              'evidence_origin': 'unknown', 'native_provenance_verified': False}
    try:
        observation = execute(command)
        (out / 'transport.stdout').write_bytes(observation.pop('stdout'))
        (out / 'transport.stderr').write_bytes(observation.pop('stderr'))
        write(out / 'transport.json', observation)
        files = decode_stream((out / 'transport.stdout').read_bytes())
        for name, data in files.items():
            (out / name).write_bytes(data)
        cap = loads(files['capture.json'])
        if (cap.get('status') == 'NOT_RUN' and observation['exit'] == 77
                and cap.get('token') == token and observation['error'] is None):
            result.update(verdict='NOT_RUN', reason=cap.get('error'), evidence_origin=cap.get('evidence_origin'))
        else:
            if observation['exit'] != 0 or observation['error'] or (out / 'transport.stderr').read_bytes():
                raise ValueError('capture transport failed or was incomplete')
            materialize_native(out, files, invocation)
            from .adapters.qnx_native import evaluate
            result = evaluate(out)
    except FileNotFoundError as exc:
        result.update(verdict='NOT_RUN', reason='launcher or capture prerequisite missing: ' + str(exc))
    except (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        result.update(reason=f'{type(exc).__name__}: {exc}')
    if not (out / 'manifest.json').exists():
        seal(out, sorted(p.name for p in out.iterdir() if p.is_file()))
    result.update(adapter='qnx-native', mode=mode, collector='c-capture-v1')
    write(out / 'result.json', result)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('scenario', type=Path)
    p.add_argument('--bin', required=True, help='absolute binary directory on the target')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--ssh', help='existing approved SSH alias; no auto provisioning')
    p.add_argument('--mode', choices=('reference', 'ignore_unblock'), default='reference')
    a = p.parse_args()
    result = run_native(loads(a.scenario.read_bytes()), a.mode, a.out, a.bin, ssh=a.ssh)
    print(json.dumps(result, indent=2))
    return 77 if result['verdict'] == 'NOT_RUN' else 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
