"""Tests the scaffold's rejection behavior, not the nonexistent application."""
import json, math, os, pathlib, subprocess, sys, unittest
import contextlib, io, tempfile
from unittest.mock import patch
import live
from run import compare
ROOT=pathlib.Path(__file__).resolve().parents[2]

class HarnessTests(unittest.TestCase):
    def test_missing_field_fails(self):
        with self.assertRaises(AssertionError): compare({}, {'advice':'Possible'}, {})
    def test_wrong_outcome_fails(self):
        with self.assertRaises(AssertionError): compare({'advice':'Worth a look'}, {'advice':'Possible'}, {})
    def test_boolean_is_not_number(self):
        with self.assertRaises(AssertionError): compare({'value':True}, {'value':1}, {})
    def test_nan_rejected(self):
        with self.assertRaises(AssertionError): compare({'elevation_deg':math.nan}, {'elevation_deg':5}, {'elevation_deg':.1})
    def test_geometry_tolerance(self):
        compare({'azimuth_deg':359.99}, {'azimuth_deg':.01}, {'azimuth_deg':.1})
        with self.assertRaises(AssertionError): compare({'elevation_deg':5.2}, {'elevation_deg':5}, {'elevation_deg':.1})
    def test_time_tolerance(self):
        compare({'sunrise':'2026-10-13T11:18:00Z'}, {'sunrise':'2026-10-13T11:17:00Z'}, {'sunrise':120})
        with self.assertRaises(AssertionError): compare({'sunrise':'2026-10-13T11:19:01Z'}, {'sunrise':'2026-10-13T11:17:00Z'}, {'sunrise':120})
    def test_missing_implementation_nonzero(self):
        env=dict(os.environ);env.pop('LV_ACCEPTANCE_COMMAND',None)
        p=subprocess.run([sys.executable,str(ROOT/'tests/acceptance/run.py')],env=env,capture_output=True,text=True)
        self.assertEqual(p.returncode,1);self.assertIn('MISSING_IMPLEMENTATION',p.stdout)
    def test_empty_suite_nonzero(self):
        p=subprocess.run([sys.executable,str(ROOT/'tests/acceptance/run.py'),'--suite','unknown','--adapter',json.dumps([sys.executable,'-c','print("{}")'])],capture_output=True,text=True)
        self.assertEqual(p.returncode,1);self.assertIn('EMPTY_SUITE',p.stdout)
    def test_unavailable_provider_is_blocked(self):
        with tempfile.TemporaryDirectory() as d, patch.object(live,'ROOT',pathlib.Path(d)), patch.object(live.requests,'get',side_effect=live.requests.ConnectionError('synthetic unavailable')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(live.main(),2)
            report=json.loads((pathlib.Path(d)/'evidence/live-latest.json').read_text())
            self.assertTrue(all(x['status']=='blocked' for x in report['checks']))
    def test_provider_schema_drift_fails(self):
        class Response:
            status_code=200
            def json(self): return {}
        with tempfile.TemporaryDirectory() as d, patch.object(live,'ROOT',pathlib.Path(d)), patch.object(live.requests,'get',return_value=Response()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(live.main(),1)

if __name__=='__main__': unittest.main()
