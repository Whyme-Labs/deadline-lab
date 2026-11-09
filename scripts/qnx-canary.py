#!/usr/bin/env python3
"""Native-target-only runner. Includes independent virtual-effect observations."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deadline_lab.adapters.qnx_native import DEFAULT_SCENARIO, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bin', type=Path, default=Path('build-qnx'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--scenario', type=Path)
    parser.add_argument('--repetitions', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 20:
        parser.error('repetitions must be 1..20')
    scenario = json.loads(args.scenario.read_text()) if args.scenario else DEFAULT_SCENARIO
    args.out.mkdir(parents=True, exist_ok=False)
    results = []
    for i in range(args.repetitions):
        for mode in ('reference', 'ignore_unblock'):
            result = run(scenario, mode, args.out / f'{i}-{mode}', args.bin)
            results.append(result)
            if result['verdict'] == 'NOT_RUN':
                (args.out / 'summary.json').write_text(json.dumps({'results': results, 'qnx_executed': False}, indent=2)+'\n')
                print(json.dumps(result, indent=2)); return 77
    expectations = all(r['verdict'] == ('PASS' if r['mode'] == 'reference' else 'FAIL') and
                       (r['mode'] != 'ignore_unblock' or 'cancel_before_effect' in r['properties'])
                       for r in results)
    summary = {'results': results, 'qnx_executed': True, 'expectations_met': expectations}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))
    return 0 if expectations else 1

if __name__ == '__main__':
    raise SystemExit(main())
