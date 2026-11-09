"""Bounded artifact manifests. Integrity detects accidents, not an adversarial author."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(directory: Path, names: list[str]) -> None:
    entries = {name: digest(directory / name) for name in names}
    (directory / 'manifest.json').write_text(json.dumps({'schema': 2, 'files': entries}, indent=2) + '\n')


def verify(directory: Path, required: set[str]) -> None:
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('schema') != 2 or not isinstance(manifest.get('files'), dict):
        raise ValueError('invalid evidence manifest')
    files = manifest['files']
    if not required.issubset(files) or len(files) > 100:
        raise ValueError('missing required evidence')
    base = directory.resolve()
    for name, expected in files.items():
        if not isinstance(name, str) or Path(name).name != name or name in {'.', '..'}:
            raise ValueError('unsafe artifact path')
        path = base / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('missing artifact or symbolic link')
        if path.stat().st_size > 16_000_000 or digest(path) != expected:
            raise ValueError('evidence digest mismatch')
