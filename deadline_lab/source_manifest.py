"""Stable source identity; no Git, SDK or external packages required."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOTS = ('deadline_lab', 'include', 'src', 'qnx', 'tests', 'scripts', 'examples', 'regressions', 'docs')
TOP = ('CMakeLists.txt', 'Makefile', 'README.md', 'LICENSE', 'SECURITY.md', 'THIRD_PARTY.md', 'CHANGELOG.md', '.gitignore')
SUFFIXES = {'.py', '.c', '.h', '.cmake', '.sh', '.json', '.md', '.toml', '.txt'}
REQUIRED = {'scripts/build-qnx.sh', 'scripts/qnx-canary.py', 'scripts/qnx-reduce.py',
            'scripts/verify-local.sh', 'scripts/verify-external.sh', 'qnx/client.c',
            'qnx/server.c', 'qnx/toolchain.cmake', 'CMakeLists.txt',
            'scripts/verify-native.sh', 'scripts/package-release.py', 'qnx/abi_probe.c',
            'deadline_lab/native_build.py', 'deadline_lab/native_gate.py', 'deadline_lab/native_workflow.py',
            'src/capture.c', 'src/sha256.c', 'include/dl_sha256.h', 'deadline_lab/capture.py',
            'deadline_lab/capture_campaign.py', 'scripts/verify-capture.sh', 'tests/test_capture.py'}


def source_paths(root: Path) -> list[Path]:
    if any((root / name).is_symlink() for name in TOP + ROOTS):
        raise ValueError('source roots and top-level files cannot be symlinks')
    found = {root / name for name in TOP if (root / name).is_file()}
    for name in ROOTS:
        for p in (root / name).rglob('*'):
            if '__pycache__' in p.parts or p.suffix not in SUFFIXES:
                continue
            if p.is_symlink():
                raise ValueError('source symlinks are not distributable')
            if p.is_file():
                found.add(p)
    names = {p.relative_to(root).as_posix() for p in found}
    if not REQUIRED <= names:
        raise ValueError('source package missing required files: ' + ', '.join(sorted(REQUIRED - names)))
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def manifest(root: Path, *, executable_only: bool = False) -> dict:
    paths = source_paths(root)
    if executable_only:
        paths = [p for p in paths if (p.relative_to(root).parts[0] not in {'docs', 'examples', 'regressions'}
                     and p.suffix in {'.py', '.c', '.h', '.cmake', '.sh'}) or p.name == 'CMakeLists.txt']
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    canonical = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'schema': 1, 'files': files, 'source_set_sha256': hashlib.sha256(canonical).hexdigest(),
            'scope': 'executable-source' if executable_only else 'source-distribution'}


def verify(root: Path, expected: dict, *, executable_only: bool = False) -> None:
    if expected != manifest(root, executable_only=executable_only):
        raise ValueError('source identity mismatch')
