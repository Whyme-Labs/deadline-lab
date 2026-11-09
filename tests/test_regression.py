import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from deadline_lab.regression import export_suite,run_suite
from deadline_lab.runner import ROOT

class RegressionTests(unittest.TestCase):
    def test_exported_suite_passes_reference_and_detects_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            witness={'mode':'omit_cancel','property':'cancel_acknowledged',
                     'scenario':json.loads((ROOT/'examples/cancel.json').read_text())}
            suite=export_suite([witness],root/'suite')
            good=run_suite(suite,root/'good',verify_mutants=True)
            self.assertTrue(good['passed'])
            self.assertEqual(2,good['checks'])
            bad=run_suite(suite,root/'bad',candidate_mode='omit_cancel')
            self.assertFalse(bad['passed'])
            xml=ET.parse(root/'bad/junit.xml').getroot()
            self.assertEqual('1',xml.attrib['failures'])
            self.assertIsNotNone(xml.find('./testcase/failure'))

    def test_suite_cannot_load_file_outside_its_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'sub').mkdir()
            (root/'outside.json').write_text('{}')
            suite=root/'sub/suite.json'
            suite.write_text(json.dumps({'schema':1,'cases':[{'scenario':'../outside.json'}]}))
            with self.assertRaises(ValueError):
                run_suite(suite,root/'out')
