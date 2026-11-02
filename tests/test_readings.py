"""Tests focus on statistics correctness and the device-command boundary."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'frizzlife_readonly'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load('readings')
p = load('protocol')


class ReadingsTests(unittest.TestCase):
    def test_live_verified_daily_sample(self):
        dps = {'102':'metric_unit','103':1810,'104':44,'105':0,'15':456}
        self.assertAlmostEqual(r.decode(dps,'water_today'),0.181)
        self.assertEqual(r.decode(dps,'reported_104'),44)
        self.assertIsNone(r.decode(dps,'water_yesterday'))
        self.assertEqual(r.decode(dps,'pressure',0.1),45.6)
        self.assertEqual(r.decode(dps,'flow'),0)

    def test_us_gallons_normalise_to_same_metric_quantity(self):
        metric = r.decode({'102':'metric_unit','103':37854.11784},'water_today')
        imperial = r.decode({'102':'us_units','103':10000},'water_today')
        self.assertAlmostEqual(metric,imperial)
        self.assertAlmostEqual(r.decode({'102':'us_units','105':1000},'flow'),3.785411784)

    def test_unknown_units_and_bad_values_stay_unavailable(self):
        for value in (True,False,'1810',None,-1,float('nan'),float('inf')):
            self.assertIsNone(r.decode({'102':'metric_unit','103':value},'water_today'))
        self.assertIsNone(r.decode({'103':1810},'water_today'))
        self.assertIsNone(r.decode({'102':'unknown','103':1810},'water_today'))
        self.assertIsNone(r.decode({'15':456},'pressure'))

    def test_reset_is_reported_not_artificially_accumulated(self):
        self.assertEqual(r.decode({'102':'metric_unit','103':0},'water_today'),0)
        self.assertIsNone(r.decode({},'water_today'))

    def test_status_queries_only(self):
        device = p.ReadOnlyDevice('test-device','127.0.0.1','0123456789abcdef',version=3.3)
        self.assertEqual(device.generate_payload(p.commands.DP_QUERY).cmd,p.commands.DP_QUERY)
        for cmd in (p.commands.CONTROL,p.commands.CONTROL_NEW,p.commands.UPDATEDPS,p.commands.AP_CONFIG):
            with self.assertRaises(ValueError):device.generate_payload(cmd)
        device.dev_type='device22'
        with self.assertRaises(ValueError):device.generate_payload(p.commands.DP_QUERY)

    def test_poll_closes_socket_even_on_failure_and_attempts_once(self):
        with patch.object(p,'ReadOnlyDevice') as cls:
            cls.return_value.status.return_value={'Err':'901'}
            with self.assertRaises(ValueError):p.read_status({'device_id':'test','host':'127.0.0.1','local_key':'test'})
            cls.return_value.set_socketRetryLimit.assert_called_once_with(1)
            cls.return_value.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
