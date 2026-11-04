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
m = load('manual_control')


class ReadingsTests(unittest.TestCase):
    def test_live_verified_daily_sample(self):
        dps = {'102':'metric_unit','103':1810,'104':44,'105':0,'15':456}
        self.assertAlmostEqual(r.decode(dps,'water_today'),0.181)
        self.assertEqual(r.decode(dps,'reported_104'),44)
        self.assertIsNone(r.decode(dps,'water_yesterday'))
        self.assertEqual(r.decode(dps,'pressure',0.1),45.6)
        self.assertAlmostEqual(r.decode(dps,'pressure_bar',0.1),3.144009325684608)
        self.assertIsNone(r.decode({},'pressure_bar',0.1))
        self.assertIsNone(r.decode(dps,'pressure_bar'))
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

    def test_fault_flags_decode_independently_and_reject_invalid_bitmaps(self):
        for key, bit in r.FAULT_BITS.items():
            for active_bit in range(7):
                self.assertEqual(r.decode({'24':1 << active_bit},key),bit == active_bit)
            self.assertFalse(r.decode({'24':0},key))
            for value in (None,True,-1,'1',1.0):
                self.assertIsNone(r.decode({'24':value},key))

    def test_extra_diagnostics_keep_codes_and_values_unscaled(self):
        dps={'109':'AUTO','110':'mode2','111':'mode4','112':10,'115':'2','118':True,'119':'9','121':82,'122':243,'127':300}
        for key, expected in {'mode_group':'Automatic','smart_mode':'Mode 2','pro_mode':'Mode 4',
                              'mode4_time_raw':10,'mode4_flow_code':'2','low_flow_enabled':True,
                              'low_flow_code':'9','leak_duration_raw':82,'leak_volume_raw':243,'test_remaining_raw':300}.items():
            self.assertEqual(r.decode(dps,key),expected)
            self.assertIsNone(r.decode({},key))
        for key, dp, invalid in [('mode_group','109',[]),('smart_mode','110','mode4'),
                                  ('pro_mode','111','mode1'),('mode4_flow_code','115','27'),
                                  ('low_flow_code','119','10'),('low_flow_enabled','118',1)]:
            self.assertIsNone(r.decode({dp:invalid},key))

    def test_manual_valve_guards_and_command_whitelist(self):
        for enabled, confirmed, online, current in [(False,True,True,'Open'),(True,False,True,'Open'),(True,True,False,'Open'),(True,True,True,None)]:
            with self.assertRaises(ValueError):
                m.validate_manual_request(enabled, confirmed, online, current, 'Closed')
        self.assertFalse(m.validate_manual_request(True,True,True,'Open','Open'))
        self.assertTrue(m.validate_manual_request(True,True,True,'Open','Closed'))
        device = m.ManualValveDevice('test','127.0.0.1','0123456789abcdef',version=3.3)
        payload = device.generate_payload(p.commands.CONTROL, {'1':False})
        self.assertIn(b'"1":false', payload.payload)
        for data in ({'101':False},{'1':1},{'1':True,'101':True},None):
            with self.assertRaises(ValueError): device.generate_payload(p.commands.CONTROL,data)
        for command in (p.commands.DP_QUERY,p.commands.UPDATEDPS,p.commands.AP_CONFIG):
            with self.assertRaises(ValueError): device.generate_payload(command,{'1':False})
        with patch.object(m,'ManualValveDevice') as cls:
            cls.return_value.set_value.return_value = {'Error':'offline'}
            with self.assertRaises(ValueError): m.set_manual_valve({'host':'127.0.0.1','device_id':'test','local_key':'test'},False)
            cls.return_value.set_value.assert_called_once_with('1',False)
            cls.return_value.close.assert_called_once()

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
