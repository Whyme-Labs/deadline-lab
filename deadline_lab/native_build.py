"""Licensed SDK build entry point. Missing prerequisites are NOT_RUN, not a pass.

No SDK acquisition, licence acceptance, network access or QNX header substitutes.
"""
from __future__ import annotations
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from .evidence import digest
from .source_manifest import manifest

ROOT = Path(__file__).resolve().parents[1]


def prerequisites() -> dict:
    tools = {name: shutil.which(name) for name in ('qcc', 'cmake')}
    directories = {name: bool(os.environ.get(name)) and Path(os.environ[name]).is_dir()
                   for name in ('QNX_HOST', 'QNX_TARGET')}
    missing = [name for name, path in tools.items() if not path]
    missing += [name for name, ok in directories.items() if not ok]
    return {'schema': 1, 'status': 'NOT_RUN' if missing else 'READY_TO_ATTEMPT',
            'qnx_compiled': False, 'qnx_executed': False,
            'host': {'system': platform.system(), 'machine': platform.machine()},
            'tools_found': {name: bool(path) for name, path in tools.items()},
            'sdk_directories_valid': directories, 'missing': missing,
            'limits': 'Prerequisite presence is not licence validation or successful compilation.'}


def check_elf(path: Path, variant: str) -> dict:
    b = path.read_bytes()[:64]
    expected_machine = 183 if 'aarch64' in variant else 62 if 'x86_64' in variant else None
    if len(b) < 64 or b[:4] != b'\x7fELF' or b[4] != 2 or b[5] not in (1, 2):
        raise ValueError('expected a 64-bit ELF binary: ' + path.name)
    machine = int.from_bytes(b[18:20], 'little' if b[5] == 1 else 'big')
    if expected_machine is None or machine != expected_machine:
        raise ValueError('ELF architecture does not match requested QNX variant')
    return {'sha256': digest(path), 'bytes': path.stat().st_size, 'elf_machine': machine}


def build(out: Path, variant: str, check_only: bool = False) -> dict:
    if not re.fullmatch(r'gcc_nto(?:x86_64|aarch64le)', variant):
        raise ValueError('supported variants: gcc_ntox86_64, gcc_ntoaarch64le')
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = prerequisites()
    result['variant'] = variant
    source = manifest(ROOT, executable_only=True)
    result['source_set_sha256'] = source['source_set_sha256']
    (out / 'source-manifest.json').write_text(json.dumps(source, indent=2) + '\n')
    commands = []
    result['commands'] = commands
    if result['missing'] or check_only:
        (out / 'build-record.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
    bdir = out / 'build'
    cmds = [
        ['qcc', '-V'],
        ['cmake', '-S', str(ROOT), '-B', str(bdir),
         '-DCMAKE_TOOLCHAIN_FILE=' + str(ROOT / 'qnx/toolchain.cmake'),
         '-DDL_QNX_VARIANT=' + variant, '-DCMAKE_BUILD_TYPE=Debug'],
        ['cmake', '--build', str(bdir), '--parallel', '2'],
    ]
    try:
        for i, cmd in enumerate(cmds):
            log = out / f'build-step-{i}.log'
            with log.open('wb') as stream:
                done = subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT,
                                      cwd=ROOT, timeout=300, check=False)
            commands.append({'argv': cmd, 'exit': done.returncode,
                             'log': log.name, 'log_sha256': digest(log)})
            if done.returncode:
                raise RuntimeError('QNX build command failed; inspect ' + log.name)
        if manifest(ROOT, executable_only=True) != source:
            raise RuntimeError('source changed during build')
        binaries = {n: check_elf(bdir / n, variant) for n in
                    ('dl-qnx-server', 'dl-qnx-client', 'dl-qnx-abi', 'dl-capture', 'dl-core-tests', 'dl-effect-tests', 'dl-sha256-tests')}
        result.update(status='COMPILED', qnx_compiled=True, binaries=binaries,
                      compiler_sha256=digest(Path(shutil.which('qcc'))))
        # Copy provenance beside binaries for the target collector. No SDK files.
        (bdir / 'build-record.json').write_text(json.dumps(result, indent=2) + '\n')
        (bdir / 'source-manifest.json').write_text(json.dumps(source, indent=2) + '\n')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        result.update(status='BUILD_FAILED', qnx_compiled=False, error=f'{type(exc).__name__}: {exc}')
    (out / 'build-record.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--variant', default=os.environ.get('DL_QNX_VARIANT', 'gcc_ntox86_64'))
    p.add_argument('--check', action='store_true', help='inspect prerequisites; do not compile')
    a = p.parse_args()
    result = build(a.out, a.variant, a.check)
    print(json.dumps(result, indent=2))
    if result['status'] == 'NOT_RUN':
        return 77
    return 0 if result['status'] in {'READY_TO_ATTEMPT', 'COMPILED'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
