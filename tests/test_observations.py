import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import sys
import types
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'frizzlife_readonly'
package = types.ModuleType('frizz_test')
package.__path__ = [str(ROOT)]
sys.modules['frizz_test'] = package


def load(name):
    spec = importlib.util.spec_from_file_location('frizz_test.' + name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


obs, analytics, alerts = load('observations'), load('analytics'), load('alerts')


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo('Europe/London')
        self.start = datetime(2026, 11, 3, tzinfo=self.tz)

    def test_continuous_flow_requires_actual_observations_and_resets_after_gap(self):
        ledger = obs.ObservationLedger()
        for minute in range(62):
            ledger.record(self.start + timedelta(minutes=minute), True, .1, 10, 3)
        result = ledger.live(self.start + timedelta(minutes=61), {})
        self.assertTrue(result['sustained_flow'])
        self.assertTrue(result['overnight_flow'])
        self.assertEqual(result['flow_run_minutes'], 61)
        ledger.record(self.start + timedelta(minutes=65), True, .2, 10, 4)
        self.assertEqual(ledger.live(self.start + timedelta(minutes=65), {})['flow_run_minutes'], 0)
        self.assertIsNone(ledger.live(self.start + timedelta(minutes=65), {})['sustained_flow'])
        ledger.record(self.start + timedelta(minutes=66), False)
        self.assertIsNone(ledger.live(self.start + timedelta(minutes=66), {})['sustained_flow'])
        self.assertIsNone(ledger.live(self.start + timedelta(minutes=66), {})['overnight_flow'])

    def test_restart_does_not_restore_continuous_flow_run(self):
        ledger = obs.ObservationLedger()
        ledger.record(self.start, True, .1, 10, 3)
        restored = obs.ObservationLedger(ledger.dump())
        restored.record(self.start + timedelta(minutes=1), True, .1, 10, 3)
        self.assertEqual(restored.live(self.start + timedelta(minutes=1), {})['flow_run_minutes'], 0)

    def test_coverage_is_bounded_and_requires_full_day_with_no_long_gap(self):
        ledger = obs.ObservationLedger()
        for sec in range(0, 86401, 30):
            ledger.record(self.start + timedelta(seconds=sec), True, .1, 0, 3)
        self.assertTrue(ledger.usable_day(self.start.date(), self.tz))
        self.assertEqual(ledger.coverage(self.start.timestamp(), (self.start + timedelta(days=1)).timestamp()), 100)
        gap = obs.ObservationLedger()
        for sec in range(0, 86401, 30):
            if 3600 <= sec < 3900:
                continue
            gap.record(self.start + timedelta(seconds=sec), True, .1, 0, 3)
        self.assertFalse(gap.usable_day(self.start.date(), self.tz))
        self.assertLess(gap.coverage(self.start.timestamp(), (self.start + timedelta(days=1)).timestamp()), 100)
        failures = obs.ObservationLedger()
        for sec in range(0, 86401, 30):
            failures.record(self.start + timedelta(seconds=sec), not 3600 <= sec < 3840, .1, 0, 3)
        self.assertGreater(failures.coverage(self.start.timestamp(), (self.start + timedelta(days=1)).timestamp()), 99)
        self.assertFalse(failures.usable_day(self.start.date(), self.tz))

    def test_dst_coverage_and_day_boundaries(self):
        start = datetime(2026, 10, 25, tzinfo=self.tz)
        end = datetime(2026, 10, 26, tzinfo=self.tz)
        parts = list(obs.day_parts(start.timestamp(), end.timestamp(), self.tz))
        self.assertEqual(parts, [('2026-10-25', 25 * 3600)])

    def test_overnight_window_crossing_midnight(self):
        ledger = obs.ObservationLedger()
        start = datetime(2026, 11, 3, 23, 40, tzinfo=self.tz)
        for minute in range(51):
            ledger.record(start + timedelta(minutes=minute), True, .1, 10, 3)
        result = ledger.live(start + timedelta(minutes=50), {'night_start_hour':22,'night_end_hour':6})
        self.assertTrue(result['overnight_flow'])
        self.assertEqual(result['night_flow_minutes'], 50)

    def test_pressure_summaries_are_observed_samples_and_missing_is_not_zero(self):
        ledger = obs.ObservationLedger()
        ledger.record(self.start, True, .1, 0, 3)
        ledger.record(self.start + timedelta(seconds=30), True, .1, 0, 4)
        ledger.record(self.start + timedelta(seconds=60), False)
        result = ledger.live(self.start + timedelta(seconds=60), {})
        self.assertEqual(result['pressure_min_today'], 3)
        self.assertEqual(result['pressure_max_today'], 4)
        self.assertEqual(result['pressure_mean_today'], 3.5)

    def test_scenarios_vary_usage_and_all_metered_charges_as_documented(self):
        tariff = {'water_rate':2,'sewer_rate':3,'return_percent':100,'annual_standing':100}
        result = analytics.scenarios(tariff, 1000, 2500, {})
        self.assertEqual(result['scenario_lower_usage'], 1560)
        self.assertEqual(result['scenario_higher_usage'], 2290)
        self.assertAlmostEqual(result['scenario_tariff_rise'], 2117.5)
        self.assertAlmostEqual(result['scenario_rise_saving'], 382.5)
        self.assertEqual(analytics.scenarios(tariff, None, 2500, {}), {})

    def test_usable_history_requires_both_statistics_and_observation_coverage(self):
        ledger = obs.ObservationLedger()
        end = self.start + timedelta(days=2)
        rows = [{'start': t, 'change': .01} for t in range(int(self.start.timestamp()), int(end.timestamp()), 3600)]
        summary, usable = analytics.usage_summary(rows, end, ledger, .1)
        self.assertEqual(summary['usable_days_7'], 0)
        self.assertEqual(usable, {})
        self.assertNotIn('average_7', summary)
        self.assertGreater(summary['recorded_week'], 0)

    def test_notifications_deduplicate_preserve_unknown_and_recover_once(self):
        gate = alerts.AlertGate()
        self.assertEqual(gate.evaluate({'device_leak_alarm':False}), [])
        active = gate.evaluate({'device_leak_alarm':True})
        self.assertEqual(len(active), 1)
        self.assertEqual(gate.evaluate({'device_leak_alarm':True}), [])
        self.assertEqual(gate.evaluate({'device_leak_alarm':None}), [])
        restored = alerts.AlertGate(dict(gate.states))
        self.assertEqual(restored.evaluate({'device_leak_alarm':True}), [])
        self.assertEqual(len(restored.evaluate({'device_leak_alarm':False})), 1)
        self.assertEqual(restored.evaluate({'device_leak_alarm':False}), [])


if __name__ == '__main__': unittest.main()
