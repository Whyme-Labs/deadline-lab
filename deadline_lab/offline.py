"""Prepared, pinned captures without SSH or target Python.

A trusted request stays on the host. Only our four binaries, two build records,
and a POSIX shell entry point go to the target. Import never treats a completed
transport-only fixture as native evidence. No SDK, licence or machine provisioning.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
from typing import Any

from . import capture
from .adapters.qnx_native import validate
from .evidence import seal
from .source_manifest import manifest

ROOT = Path(__file__).resolve().parents[1]
MAX_BINARY = 16_000_000
METADATA = ('build-record.json', 'source-manifest.json')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular(path: Path, limit: int) -> bytes:
    """Read a bounded regular file without following the final symlink."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('not a bounded regular file: ' + path.name)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit or len(data) != info.st_size:
            raise ValueError('file changed or exceeded bound: ' + path.name)
        return data
    finally:
        os.close(fd)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def binaries(fixture: bool) -> tuple[str, ...]:
    prefix = 'dl-transport-' if fixture else 'dl-qnx-'
    return ('dl-capture', prefix + 'server', prefix + 'client', prefix + 'abi')


def checked_request(raw: bytes) -> dict:
    doc = capture.loads(raw)
    if not isinstance(doc, dict) or set(doc) != {'request', 'request_sha256'}:
        raise ValueError('invalid offline request document')
    r = doc['request']
    if digest(canonical(r)) != doc['request_sha256']:
        raise ValueError('offline request digest mismatch')
    fields = {'schema', 'token', 'mode', 'scenario', 'transport', 'fixture',
              'expected_source_set_sha256', 'expected_binaries', 'expected_metadata',
              'budget_ms'}
    if not isinstance(r, dict) or set(r) != fields or r['schema'] != 1 or r['transport'] != 'offline-file':
        raise ValueError('unsupported offline request')
    if (type(r['fixture']) is not bool or not isinstance(r['expected_source_set_sha256'], str) or
            not re.fullmatch('[a-f0-9]{64}', r['expected_source_set_sha256'])):
        raise ValueError('request origin or source identity invalid')
    capture.capture_command('/absolute/target', r['mode'], r['scenario'], r['token'],
                            fixture=r['fixture'], budget_ms=r['budget_ms'])
    if (not isinstance(r['expected_binaries'], dict) or not isinstance(r['expected_metadata'], dict) or
            set(r['expected_binaries']) != set(binaries(r['fixture'])) or set(r['expected_metadata']) != set(METADATA)):
        raise ValueError('request file set invalid')
    for group in ('expected_binaries', 'expected_metadata'):
        for identity in r[group].values():
            if (not isinstance(identity, dict) or set(identity) != {'sha256', 'bytes'} or
                not isinstance(identity['sha256'], str) or not re.fullmatch('[a-f0-9]{64}', identity['sha256']) or
                type(identity['bytes']) is not int or not 0 < identity['bytes'] <= MAX_BINARY):
                raise ValueError('request file identity invalid')
    return r


def target_script(r: dict) -> bytes:
    calls = ','.join(f'{a["work_ms"]}:{a["timeout_ms"]}' for a in r['scenario']['actions'])
    options = ['--mode', r['mode'], '--calls', calls, '--token', r['token'],
               '--stream', '--budget-ms', str(r['budget_ms'])]
    if r['fixture']:
        options.append('--transport-fixture')
    return ('''#!/bin/sh
# Generated from a host-owned request. The target never installs software.
# Requires /bin/sh, mkdir and the shipped project executables. No target Python.
set -eu
umask 077
if [ "$#" -ne 1 ]; then
    printf '%s\\n' 'usage: run-target.sh NEW_RESULT_DIRECTORY' >&2
    exit 64
fi
case "$0" in */*) HERE=${0%/*} ;; *) HERE=. ;; esac
cd -P "$HERE"
BIN=$(pwd -P)
case "$1" in /*) OUT=$1 ;; *) OUT=$BIN/$1 ;; esac
# mkdir must succeed. Never overwrite a previous capture or follow an existing link.
mkdir -m 700 "$OUT"
code=0
"$BIN/dl-capture" --bin "$BIN" ''' + shlex.join(options) + ''' >"$OUT/capture.stdout" 2>"$OUT/capture.stderr" || code=$?
printf '%s\\n' "$code" >"$OUT/capture.exit"
exit "$code"
''').encode()


def prepare(bin_dir: Path, out: Path, scenario: dict, mode: str = 'reference', *,
            fixture: bool = False, budget_ms: int = 60000) -> dict:
    """Create a fresh handoff only after verifying source and build identities.

    fixture=True is an explicit local transport test, never a QNX build record.
    All native binaries must come from an existing authorised native_build run.
    """
    validate(scenario)
    token = secrets.token_hex(16)
    capture.capture_command('/absolute/target', mode, scenario, token,
                            fixture=fixture, budget_ms=budget_ms)
    source = manifest(ROOT, executable_only=True)
    source_bytes = (json.dumps(source, indent=2, sort_keys=True) + '\n').encode()
    contents = {n: read_regular(bin_dir / n, MAX_BINARY) for n in binaries(fixture)}
    identities = {n: {'sha256': digest(b), 'bytes': len(b)} for n, b in contents.items()}
    for name in contents:
        if not os.access(bin_dir / name, os.X_OK):
            raise ValueError('target program is not executable: ' + name)
    if fixture:
        build = {'schema': 1, 'status': 'PORTABLE_TEST_ONLY', 'qnx_compiled': False,
                 'source_set_sha256': source['source_set_sha256'], 'binaries': identities}
        contents['build-record.json'] = (json.dumps(build, indent=2) + '\n').encode()
        contents['source-manifest.json'] = source_bytes
    else:
        for name in METADATA:
            contents[name] = read_regular(bin_dir / name, capture.MAX_FILE)
        build = capture.loads(contents['build-record.json'])
        actual_source = capture.loads(contents['source-manifest.json'])
        if (not isinstance(build, dict) or not isinstance(build.get('binaries'), dict) or
                build.get('status') != 'COMPILED' or build.get('qnx_compiled') is not True or
                actual_source != source or build.get('source_set_sha256') != source['source_set_sha256']):
            raise ValueError('a genuine completed native build of this source revision is required')
        for name, identity in identities.items():
            recorded = build.get('binaries', {}).get(name, {})
            if not isinstance(recorded, dict) or any(recorded.get(k) != v for k, v in identity.items()):
                raise ValueError('binary differs from native build record: ' + name)
    request = {'schema': 1, 'token': token, 'mode': mode, 'scenario': scenario,
               'transport': 'offline-file', 'fixture': fixture, 'budget_ms': budget_ms,
               'expected_source_set_sha256': source['source_set_sha256'],
               'expected_binaries': identities,
               'expected_metadata': {n: {'sha256': digest(contents[n]), 'bytes': len(contents[n])}
                                     for n in METADATA}}
    document = {'request': request, 'request_sha256': digest(canonical(request))}
    raw_request = (json.dumps(document, indent=2, sort_keys=True) + '\n').encode()
    checked_request(raw_request)
    # Validation precedes any destination creation. Failure cannot produce a ready bundle.
    out.mkdir(parents=True, exist_ok=False)
    target = out / 'target'
    target.mkdir(mode=0o700)
    for name, data in contents.items():
        p = target / name
        p.write_bytes(data)
        p.chmod(0o700 if name in binaries(fixture) else 0o600)
        if read_regular(p, MAX_BINARY) != data:
            raise ValueError('handoff copy readback mismatch')
    script = target / 'run-target.sh'
    script.write_bytes(target_script(request))
    script.chmod(0o700)
    (out / 'request.json').write_bytes(raw_request)
    (out / 'request.json').chmod(0o600)
    summary = {'schema': 1, 'status': 'TRANSPORT_TEST_READY' if fixture else 'READY_TO_RUN',
               'qnx_executed': False, 'native_gate_closed': False,
               'request_sha256': document['request_sha256'],
               'target_files': sorted([*contents, 'run-target.sh']),
               'target_programs': list(binaries(fixture)),
               'source_set_sha256': source['source_set_sha256']}
    capture.write(out / 'handoff.json', summary)
    return summary


def check_pinned_capture(files: dict[str, bytes], r: dict) -> dict:
    """Compare returned data to the original host request, not a returned request."""
    cap = capture.loads(files['capture.json'])
    if cap.get('token') != r['token'] or cap.get('policy') != r['mode']:
        raise ValueError('returned capture belongs to a different host request')
    if cap.get('status') == 'NOT_RUN':
        return cap
    # The existing portable collector deliberately omits native provenance.
    # Native imports must return both pinned records byte for byte.
    if not r['fixture']:
        for name, identity in r['expected_metadata'].items():
            data = files[name]
            if len(data) != identity['bytes'] or digest(data) != identity['sha256']:
                raise ValueError('returned build metadata differs from prepared host record: ' + name)
    observed = capture.loads(files['binaries.json'])['binaries']
    names = binaries(r['fixture'])
    for role, name in zip(('capture', 'server', 'client', 'abi'), names):
        item = observed[role]
        expected = r['expected_binaries'][name]
        if item.get('stable') is not True or any(item.get(k) != v for k, v in expected.items()):
            raise ValueError('returned binary differs from prepared host record: ' + name)
    if r['fixture'] and (cap.get('evidence_origin') != 'posix-capture-test' or cap.get('qnx_executed') is not False):
        raise ValueError('portable request cannot acquire native evidence')
    return cap


def verify_offline_import(out: Path, invocation: dict, transport: dict) -> None:
    r = checked_request(read_regular(out / 'offline-request.json', capture.MAX_FILE))
    if r['fixture'] or invocation != r:
        raise ValueError('native importer requires the original native host request')
    if (transport.get('origin') != 'offline-file' or transport.get('import_complete') is not True or
            transport.get('host_observed_launcher') is not False or
            'launcher_reaped' in transport):
        raise ValueError('offline transfer cannot claim a host-observed remote process')
    raw_exit = read_regular(out / 'capture.exit', 4)
    if raw_exit != b'0\n' or transport.get('exit') != 0:
        raise ValueError('target wrapper did not record successful completion')
    files = capture.decode_stream(read_regular(out / 'transport.stdout', capture.MAX_STREAM))
    check_pinned_capture(files, r)


def ingest(request_path: Path, results: Path, out: Path) -> dict:
    """Import one completed or incomplete capture. Never closes the full QNX gate."""
    request_raw = read_regular(request_path, capture.MAX_FILE)
    r = checked_request(request_raw)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'offline-request.json').write_bytes(request_raw)
    capture.write(out / 'invocation.json', r)
    result = {'verdict': 'INCONCLUSIVE', 'adapter': 'qnx-native', 'mode': r['mode'],
              'collector': 'c-capture-v1', 'transport': 'offline-file',
              'qnx_executed': False, 'native_gate_closed': False, 'properties': [],
              'native_provenance_verified': False, 'evidence_origin': 'unknown'}
    try:
        stdout = read_regular(results / 'capture.stdout', capture.MAX_STREAM)
        (out / 'transport.stdout').write_bytes(stdout)
        stderr = read_regular(results / 'capture.stderr', capture.MAX_FILE)
        (out / 'transport.stderr').write_bytes(stderr)
        raw_exit = read_regular(results / 'capture.exit', 4)
        (out / 'capture.exit').write_bytes(raw_exit)
        if not re.fullmatch(rb'(0|[1-9][0-9]{0,2})\n', raw_exit) or int(raw_exit) > 255:
            raise ValueError('invalid target completion record')
        code = int(raw_exit)
        transport = {'origin': 'offline-file', 'exit': code, 'error': None,
                     'import_complete': True, 'host_observed_launcher': False}
        capture.write(out / 'transport.json', transport)
        files = capture.decode_stream(stdout)
        cap = check_pinned_capture(files, r)
        for name, data in files.items():
            (out / name).write_bytes(data)
        if cap.get('status') == 'NOT_RUN' and code == 77 and not stderr:
            result.update(verdict='NOT_RUN', reason=cap.get('error'),
                          evidence_origin=cap.get('evidence_origin'))
        else:
            if code or stderr or cap.get('status') != 'COMPLETE' or cap.get('error') is not None:
                raise ValueError('target capture failed or did not complete cleanly')
            if r['fixture']:
                if (cap.get('server_reaped') is not True or cap.get('current_reaped') is not True or
                        cap.get('server_exit') != 0 or cap.get('observer_exit') != 0):
                    raise ValueError('portable target child completion missing')
                expected = r['scenario']['actions'] + [{'work_ms': 1, 'timeout_ms': 1500}]
                calls = cap.get('calls', [])
                if len(calls) != len(expected) or any(
                    c.get('id') != i or c.get('work_ms') != a['work_ms'] or
                    c.get('timeout_ms') != a['timeout_ms'] or c.get('attempted') is not True or c.get('exit') != 0
                    for i, (c, a) in enumerate(zip(calls, expected), 1)):
                    raise ValueError('portable target calls differ from request')
                effects = capture.normalized_effects(files['effects.raw.jsonl'])
                result.update(verdict='TRANSPORT_ONLY', evidence_origin='posix-capture-test',
                              observed_effects=effects[-1]['effect_count'],
                              reason='Portable transport exercised. No native application verdict.')
            else:
                capture.materialize_native(out, files, r)
                from .adapters.qnx_native import evaluate
                result.update(evaluate(out))
                result['native_gate_closed'] = False
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result.update(reason=f'{type(exc).__name__}: {exc}')
    if not (out / 'manifest.json').exists():
        seal(out, sorted(p.name for p in out.iterdir() if p.is_file()))
    capture.write(out / 'result.json', result)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare', help='package an existing genuine native build')
    prep.add_argument('--bin', type=Path, required=True)
    prep.add_argument('--out', type=Path, required=True)
    prep.add_argument('--scenario', type=Path, default=ROOT / 'examples/native/unblock.json')
    prep.add_argument('--mode', choices=('reference', 'ignore_unblock'), default='reference')
    imp = sub.add_parser('ingest', help='check returned files against the original host request')
    imp.add_argument('--request', type=Path, required=True)
    imp.add_argument('--results', type=Path, required=True)
    imp.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.bin, args.out, capture.loads(args.scenario.read_bytes()), args.mode)
        else:
            result = ingest(args.request, args.results, args.out)
    except FileNotFoundError as exc:
        print(json.dumps({'status': 'NOT_RUN', 'reason': str(exc), 'native_gate_closed': False}))
        return 77
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'ERROR', 'reason': str(exc), 'native_gate_closed': False}))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result.get('status') == 'READY_TO_RUN' or result.get('verdict') == 'PASS' else 77 if result.get('verdict') == 'NOT_RUN' else 1


if __name__ == '__main__':
    raise SystemExit(main())
