"""Test metodologici con unittest: nessuna dipendenza oltre quelle dello script."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.generate_benchmark_plots import aggregate, load_data, main, normalize


def run(scenario='s1', run_id='r1', **kw):
    return dict(scenario=scenario, prompt='json', model='m1', run_id=run_id, **kw)


class MetricsTests(unittest.TestCase):
    def normalize(self, rows, checks=()):
        return normalize(pd.DataFrame(rows), pd.DataFrame(checks), [])[0]

    def test_macro_weights_scenarios_micro_weights_tests(self):
        data = self.normalize([run(passed_tests=1, evaluated_tests=1, completed=True),
                               run('s2', passed_tests=0, evaluated_tests=9, completed=True)])
        row = aggregate(data, ['prompt']).iloc[0]
        self.assertAlmostEqual(row.macro_rate, .5)
        self.assertAlmostEqual(row.micro_rate, .1)
        self.assertAlmostEqual(row.full_success_rate, .5)
        self.assertEqual(row.scenarios, 2)
        self.assertEqual(row.evaluated_tests, 10)

    def test_repeats_do_not_overweight_scenario(self):
        data = self.normalize([run(run_id='a', passed_tests=1, evaluated_tests=1),
                               run(run_id='b', passed_tests=1, evaluated_tests=1),
                               run('s2', passed_tests=0, evaluated_tests=1)])
        row = aggregate(data, ['prompt']).iloc[0]
        self.assertAlmostEqual(row.macro_rate, .5)
        self.assertAlmostEqual(row.micro_rate, 2/3)
        self.assertEqual(row.runs, 3)

    def test_full_success_requires_completion(self):
        data = self.normalize([run(passed_tests=2, evaluated_tests=2),
                               run('s2', passed_tests=2, evaluated_tests=2, expected_tests=3, completed=True),
                               run('s3', passed_tests=2, evaluated_tests=2, completed=True)])
        self.assertTrue(data.full_success.iloc[:2].isna().all())
        self.assertEqual(data.full_success.iloc[2], 1)

    def test_missing_invalid_zero_and_nonfinite(self):
        data = self.normalize([run(passed_tests=0, evaluated_tests=0),
                               run('s2', passed_tests=3, evaluated_tests=2),
                               run('s3', passed_tests='inf', evaluated_tests=2),
                               run('s4', passed_tests=1.5, evaluated_tests=2)])
        self.assertTrue(data.test_rate.isna().all())

    def test_skipped_and_error_are_not_failures(self):
        checks = [run(check_id=str(i), check_type='DNSRecordCheck', outcome=o)
                  for i, o in enumerate(['pass', 'fail', 'error', 'skipped'])]
        data = self.normalize([run(completed=True)], checks)
        self.assertEqual(data.evaluated_tests.iloc[0], 2)
        self.assertEqual(data.test_rate.iloc[0], .5)
        self.assertTrue(pd.isna(data.full_success.iloc[0]))

    def test_count_mismatch_does_not_fabricate_score(self):
        data = self.normalize([run(passed_tests=2, evaluated_tests=2, completed=True)],
                              [run(check_id='c', check_type='A', outcome='fail')])
        self.assertTrue(data.test_rate.isna().all())

    def test_duplicate_run_keys_are_excluded(self):
        self.assertTrue(self.normalize([run(), run()]).empty)

    def test_inconsistent_metadata_is_excluded(self):
        data = self.normalize([run(category='A', devices=2), run(run_id='b', category='B', devices=3)])
        self.assertTrue(data.category.isna().all())
        self.assertTrue(data.devices.isna().all())

    def test_mapping_nested_json_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'good.json').write_text(json.dumps({'results': [dict(lab='s', p='json', model='m', id='1')]}))
            (root/'bad.json').write_text('{bad')
            config = {'sources': [{'glob': '*.json', 'kind': 'runs', 'records_path': 'results',
                                   'columns': {'scenario': 'lab', 'prompt': 'p', 'run_id': 'id'}}]}
            log = []
            runs, checks = load_data(root, config, log, root/'out')
            self.assertEqual(len(runs), 1)
            self.assertTrue(checks.empty)
            self.assertTrue(any('ESCLUSO' in line for line in log))

    def test_cli_empty_input_writes_explanatory_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'input'
            source.mkdir()
            out = Path(tmp)/'out'
            self.assertEqual(main(['--input', str(source), '--output', str(out)]), 2)
            self.assertIn('Nessun risultato utilizzabile', (out/'summary.md').read_text())
            self.assertTrue((out/'summary.csv').exists())

    def test_smoke_outputs_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'runs.csv'
            pd.DataFrame([run(passed_tests=1, evaluated_tests=1, completed=True)]).to_csv(source, index=False)
            before = source.read_bytes()
            out = Path(tmp)/'out'
            self.assertEqual(main(['--input', str(source), '--output', str(out), '--analysis', 'prompt', 'labs']), 0)
            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(list(out.rglob('*.png')))
            self.assertTrue(list(out.rglob('*.pdf')))

    def test_model_comparison_is_matched(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'runs.csv'
            rows = [run(passed_tests=1, evaluated_tests=1), run('extra', passed_tests=0, evaluated_tests=1)]
            rows.append(dict(run(passed_tests=1, evaluated_tests=1), model='m2'))
            pd.DataFrame(rows).to_csv(source, index=False)
            out = Path(tmp)/'out'
            main(['--input', str(source), '--output', str(out), '--analysis', 'models'])
            common = pd.read_csv(out/'model_comparison.csv')
            self.assertTrue(common.scenarios.eq(1).all())
            self.assertTrue(common.macro_rate.eq(1).all())


if __name__ == '__main__':
    unittest.main()
