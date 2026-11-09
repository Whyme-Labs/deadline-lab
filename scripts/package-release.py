#!/usr/bin/env python3
"""Create a complete source archive and optionally include locally recorded evidence.

Never redistribute an SDK, licence, build tree, private key or native binary.
Every selected source file is accounted for. Output must be a new path.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import stat
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deadline_lab.source_manifest import manifest, source_paths

ROOT = Path(__file__).resolve().parents[1]


def create(root: Path, output: Path, evidence: bool = False, history: bool = False) -> dict:
    selected = {p.relative_to(root).as_posix(): p.read_bytes() for p in source_paths(root)}
    if (root / '.git').exists() and shutil.which('git'):
        tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
        omitted = [n for n in tracked if n and n not in selected]
        if omitted:
            raise ValueError('tracked files omitted from release; review explicitly: ' + ', '.join(omitted))
    modes = {n: 0o755 if n.startswith('scripts/') and n.endswith(('.sh', '.py')) else 0o644
             for n in selected}
    source = manifest(root)
    selected['SOURCE_MANIFEST.json'] = (json.dumps(source, indent=2, sort_keys=True) + '\n').encode()
    if evidence:
        allowed = {'.json', '.jsonl', '.txt', '.log', '.stderr', '.stdout', '.html', '.png', '.xml', '.md', '.csv', '.conf', '.access', '.sha256'}
        for path in sorted((root / 'evidence').rglob('*')):
            if path.is_symlink():
                raise ValueError('refusing symlink in evidence')
            if path.is_file():
                permitted_state = path.parent.name == 'state-files' and path.name in {'state', 'healthy'}
                if path.suffix not in allowed and not permitted_state:
                    raise ValueError('unreviewed evidence file type: ' + path.name)
                if path.stat().st_size > 16_000_000:
                    raise ValueError('evidence file exceeds package bound')
                selected[path.relative_to(root).as_posix()] = path.read_bytes()
    if history:
        selected['source-history.bundle'] = (root / 'source-history.bundle').read_bytes()
    release = {'schema': 1, 'version': '0.5.0', 'source_files': len(source['files']),
               'source_set_sha256': source['source_set_sha256'],
               'includes_evidence': evidence, 'includes_source_history': history,
               'native_qnx_gate': 'NOT_ESTABLISHED',
               'note': 'Read evidence/v0.5.0 for current validation. No SDK or compiled binaries included.'}
    selected['RELEASE.json'] = (json.dumps(release, indent=2) + '\n').encode()
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(selected.items())}
    selected['MANIFEST.sha256'] = ''.join(f'{d}  {n}\n' for n, d in hashes.items()).encode()
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for name, data in sorted(selected.items()):
            item = zipfile.ZipInfo('deadline-lab/' + name, date_time=(2026, 11, 10, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (stat.S_IFREG | modes.get(name, 0o644)) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, data)
    # Re-open and verify before reporting a distributable artifact.
    with zipfile.ZipFile(output) as archive:
        for name, expected in hashes.items():
            if hashlib.sha256(archive.read('deadline-lab/' + name)).hexdigest() != expected:
                raise ValueError('archive readback mismatch')
        for name in source['files']:
            if 'deadline-lab/' + name not in archive.namelist():
                raise ValueError('source missing from archive')
    return {**release, 'archive_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'archive_files': len(selected), 'archive_bytes': output.stat().st_size,
            'readback_verified': True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--include-evidence', action='store_true')
    parser.add_argument('--include-history', action='store_true')
    args = parser.parse_args()
    print(json.dumps(create(ROOT, args.out, args.include_evidence, args.include_history), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
