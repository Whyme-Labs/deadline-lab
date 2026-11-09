"""Export reduced failures as executable regression suites with JUnit output."""
from __future__ import annotations
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from .runner import run_scenario


def export_suite(witnesses: list[dict[str, Any]], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=False)
    cases = []
    for witness in witnesses:
        filename = witness['mode'] + '.json'
        (directory / filename).write_text(json.dumps(witness['scenario'], indent=2) + '\n')
        cases.append({'name': witness['property'], 'scenario': filename, 'mutation': witness['mode'],
                      'required_property': witness['property']})
    suite = directory / 'suite.json'
    suite.write_text(json.dumps({'schema': 1, 'name': 'recovery-regressions', 'cases': cases}, indent=2) + '\n')
    return suite


def run_suite(suite_path: Path, out: Path, candidate_mode: str = 'reference',
              verify_mutants: bool = False, binary: Path | None = None) -> dict[str, Any]:
    suite = json.loads(suite_path.read_text())
    if suite.get('schema') != 1 or not isinstance(suite.get('cases'), list) or not 1 <= len(suite['cases']) <= 32:
        raise ValueError('invalid regression suite')
    out.mkdir(parents=True, exist_ok=False)
    root = suite_path.resolve().parent
    cases = []
    for index, spec in enumerate(suite['cases']):
        path = (root / spec['scenario']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('suite scenario must be a local file inside the suite directory')
        scenario = json.loads(path.read_text())
        executions = [(candidate_mode, 'candidate')]
        if verify_mutants:
            executions.append((spec['mutation'], 'sensitivity'))
        for mode, purpose in executions:
            result = run_scenario(scenario, mode, out / f'{index}-{purpose}', binary=binary)
            expected = (result['verdict'] == 'PASS') if purpose == 'candidate' else (
                result['verdict'] == 'FAIL' and spec['required_property'] in result['properties'])
            cases.append({'name': spec['name'], 'purpose': purpose, 'mode': mode,
                          'expected_outcome_observed': expected, 'result': result})
    failures = sum(not c['expected_outcome_observed'] for c in cases)
    inconclusive = sum(c['result']['verdict'] == 'INCONCLUSIVE' for c in cases)
    summary = {'schema': 1, 'checks': len(cases), 'failed_expectations': failures,
               'inconclusive': inconclusive, 'passed': failures == 0, 'cases': cases,
               'qnx_executed': False}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    xml = ET.Element('testsuite', name=suite.get('name', 'deadline-lab'), tests=str(len(cases)),
                     failures=str(failures - inconclusive), errors=str(inconclusive))
    for case in cases:
        node = ET.SubElement(xml, 'testcase', classname='deadline_lab.recovery',
                             name=case['name'] + '.' + case['purpose'])
        if not case['expected_outcome_observed']:
            kind = 'error' if case['result']['verdict'] == 'INCONCLUSIVE' else 'failure'
            ET.SubElement(node,kind,message='Expected regression outcome was not observed').text=json.dumps(case['result'])
        ET.SubElement(node, 'system-out').text = json.dumps(case['result'])
    ET.ElementTree(xml).write(out/'junit.xml', encoding='utf-8', xml_declaration=True)
    return summary
