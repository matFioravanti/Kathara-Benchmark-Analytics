"""Verify the zero-configuration command creates its documented output layout."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import genera_grafici
from test_real_benchmark import NativeReportsTest

class DropInFlowTest(unittest.TestCase):
    def test_default_input_and_output_are_repo_directories(self):
        self.assertEqual(genera_grafici.INPUT.name,"result")
        self.assertEqual(genera_grafici.OUTPUT.name,"grafici")

    def test_copy_csv_and_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"result"
            source.mkdir()
            NativeReportsTest().fixture(source)
            rows=pd.read_csv(source/"runs.csv")
            rows["total_seconds"]=[120,100]
            rows["total_tokens"]=[250,180]
            rows.to_csv(source/"runs.csv",index=False)
            out=root/"grafici"
            self.assertEqual(genera_grafici.main(
                ["--input",str(source),"--output",str(out),"--format","png"]),0)
            self.assertTrue((out/"LEGGIMI.txt").exists())
            self.assertTrue((out/"01_correttezza"/"skill.png").exists())
            self.assertTrue((out/"02_prompt"/"prompt.png").exists())
            self.assertTrue((out/"03_laboratori"/"lab_skill.png").exists())
            self.assertTrue((out/"05_efficienza"/"total_seconds.png").exists())
            self.assertTrue((out/"11_skill"/"confronto_appaiato.png").exists())
            self.assertTrue((out/"12_sampling"/"temperatura_copertura.png").exists())

    def test_missing_files_error(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(SystemExit) as context:
                genera_grafici.main(["--input",temp,"--output",str(Path(temp)/"charts")])
            self.assertEqual(context.exception.code,2)

if __name__=="__main__":
    unittest.main()
