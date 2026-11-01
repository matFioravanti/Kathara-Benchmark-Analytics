"""Smoke and regression tests for the native Kathara CSV adapter."""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.plot_kathara_results import read_benchmark, produce


class NativeReportsTest(unittest.TestCase):
    def fixture(self, root):
        rows=[]
        details=[]
        for mode,passed in [("no_skill",1),("dns_only",2)]:
            rid="run-"+mode
            rows.append(dict(ID=rid,lab_id="lab_01",dns_tree_id="base",task_level="small",
                             prompt_type="T1",model="m",skill_mode=mode,experiment_id="test",
                             replicate="1",reasoning_effort="low",correction_sha256="sha",
                             checks_passed=str(passed),checks_total="2",pipeline_completed="True",
                             checker_executed="True",sampling_temperature_status="unavailable"))
            for i in range(2):
                details.append(dict(ID=rid,lab_id="lab_01",dns_tree_id="base",task_level="small",
                                    prompt_type="T1",model="m",category="dns_record",
                                    test_description="Checking correctness of DNS records",
                                    passed=str(i<passed),reason="pc16 resolve MX example.com" if i>=passed else "OK"))
        pd.DataFrame(rows).to_csv(root/"runs.csv",index=False)
        pd.DataFrame(details).to_csv(root/"checks.csv",index=False)

    def test_duplicate_descriptions_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.fixture(root)
            runs,checks=read_benchmark(root)
            self.assertEqual(len(checks),4)
            self.assertEqual(checks[checks.run_id.eq("run-no_skill")].check_id.tolist(),["1","2"])
            self.assertEqual(checks.record_type.eq("MX").sum(),1)

    def test_charts_and_no_invented_sampling(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.fixture(root)
            runs,checks=read_benchmark(root)
            out=root/"analytics"
            count=produce(runs,checks,out,["png"])
            self.assertGreaterEqual(count,3)
            self.assertTrue((out/"11_skill/confronto_appaiato.png").exists())
            self.assertTrue((out/"12_sampling/temperatura_copertura.png").exists())
            self.assertFalse((out/"12_sampling/temperatura_vs_successo.png").exists())
            delta=pd.read_csv(out/"skill_paired_deltas.csv")
            self.assertAlmostEqual(delta.mean_delta_pp.iloc[0],50.)

    def test_mismatch_is_audited_without_abort(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.fixture(root)
            data=pd.read_csv(root/"runs.csv")
            data.loc[data.skill_mode.eq("no_skill"),"checks_passed"]=2
            data.to_csv(root/"runs.csv",index=False)
            runs,checks=read_benchmark(root)
            bad=runs[runs.skill_mode.eq("no_skill")].iloc[0]
            self.assertEqual(bad.data_quality_status,"count_mismatch")
            self.assertTrue(pd.isna(bad.test_rate))
            self.assertEqual(bad.reported_passed_tests,2)
            self.assertEqual(bad.detail_passed,1)
            out=root/"charts"
            produce(runs,checks,out,["png"])
            quality=pd.read_csv(out/"data_quality_issues.csv")
            self.assertEqual(len(quality),1)
            self.assertEqual(quality.run_id.iloc[0],"run-no_skill")
            self.assertEqual(len(pd.read_csv(out/"normalized_runs.csv")),2)

    def test_missing_check_details_are_reported_not_fabricated(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.fixture(root)
            rows=pd.read_csv(root/"checks.csv")
            rows=rows[rows.ID.eq("run-no_skill")]
            rows.to_csv(root/"checks.csv",index=False)
            runs,checks=read_benchmark(root)
            absent=runs[runs.skill_mode.eq("dns_only")].iloc[0]
            self.assertEqual(absent.data_quality_status,"no_detail")
            self.assertAlmostEqual(absent.test_rate,1.)

if __name__=="__main__":
    unittest.main()
