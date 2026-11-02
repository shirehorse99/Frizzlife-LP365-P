import importlib.util
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'frizzlife_readonly'
spec = importlib.util.spec_from_file_location('comparison', ROOT / 'comparison.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.catalog = c.validate_catalog(json.loads((ROOT / 'tariffs.json').read_text()))
        self.tariff = c.select_tariff(self.catalog, 'welsh_standard', date(2026, 11, 2))

    def test_published_welsh_water_one_person_example(self):
        # Supplier's 52 m³/year example rounds to £447.36 including 95% sewer return.
        result = c.calculate(self.tariff, 0, [52 / 365])
        self.assertEqual(round(result['projected_annual_cost'], 2), 447.36)
        self.assertEqual(result['annual_standing'], 210.37)
        self.assertIsNone(result['current_annual_bill'])
        self.assertNotIn('projected_annual_saving', result)
        self.assertNotIn('break_even_daily_litres', result)

    def test_break_even_and_saving_can_be_negative(self):
        result = c.calculate(self.tariff, 600, [0.2] * 7)
        self.assertAlmostEqual(result['projected_annual_cost'], 210.37 + 73 * 4.55741)
        self.assertGreater(result['projected_annual_saving'], 0)
        litres = result['break_even_daily_litres']
        at_threshold = c.calculate(self.tariff, 600, [litres / 1000] * 7)
        self.assertAlmostEqual(at_threshold['projected_annual_saving'], 0)
        self.assertLess(c.calculate(self.tariff, 300, [0.5] * 7)['projected_annual_saving'], 0)
        self.assertNotIn('comparison_result', c.calculate(self.tariff, 600, [0.2]))

    def test_expired_future_and_variant_tariffs(self):
        self.assertIsNone(c.select_tariff(self.catalog, 'welsh_standard', date(2027, 4, 1)))
        self.assertIsNone(c.select_tariff(self.catalog, 'welsh_standard', date(2026, 3, 31)))
        self.assertAlmostEqual(c.select_tariff(self.catalog, 'welsh_foul_only', date(2026, 11, 2))['annual_standing'], 164.5)
        t = c.select_tariff(self.catalog, 'welsh_water_only', date(2026, 11, 2))
        self.assertEqual(t['annual_standing'], 58.63)
        self.assertEqual(t['sewer_rate'], 0)

    def test_catalog_rejects_untrusted_or_invalid_values(self):
        for key, value in [('water_per_m3',float('nan')),('sewer_per_m3',-1),('water_standing_annual',True),
                           ('source','https://example.com/tariff'),('valid_until','2030-01-01')]:
            data = json.loads((ROOT / 'tariffs.json').read_text())
            data['tariffs'][0][key] = value
            with self.assertRaises((ValueError, TypeError)): c.validate_catalog(data)

    def test_only_full_days_and_real_dst_hour_counts(self):
        tz = ZoneInfo('Europe/London')
        for spring in (True, False):
            day = date(2026, 3, 29) if spring else date(2026, 10, 25)
            start = datetime.combine(day - timedelta(days=1), datetime.min.time(), tz)
            end = datetime.combine(day + timedelta(days=2), datetime.min.time(), tz)
            rows = [{'start': stamp, 'change': 0.01} for stamp in range(int(start.timestamp()), int(end.timestamp()), 3600)]
            values = c.complete_daily_usage(rows, end, 30)
            self.assertEqual(len(values), 2)  # First day excluded, today excluded.
            self.assertAlmostEqual(values[0], 0.23 if spring else 0.25)
            missing = [r for r in rows if r['start'] != datetime.combine(day, datetime.min.time(), tz).timestamp()]
            self.assertEqual(len(c.complete_daily_usage(missing, end, 30)), 1)

    def test_no_usage_history_does_not_fabricate_projection(self):
        result = c.calculate(self.tariff, 600, [], 0.181)
        self.assertNotIn('projected_annual_cost', result)
        self.assertEqual(result['sample_days'], 0)
        self.assertAlmostEqual(result['today_metered_cost'], 0.181 * 4.55741 + 210.37 / 365)


if __name__ == '__main__': unittest.main()
