"""Pure, indicative household tariff calculations. No device commands."""
from datetime import date, datetime, timedelta
import math
from urllib.parse import urlparse

PROFILES = {
    "welsh_standard": "Wales — Welsh Water: water and sewerage",
    "welsh_foul_only": "Wales — Welsh Water: approved surface-water rebate",
    "welsh_water_only": "Wales — Welsh Water: water only",
    "custom": "Other region / supplier — enter custom rates",
}


def finite(value, minimum=0, maximum=1_000_000):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def validate_catalog(data):
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("tariffs"), list):
        raise ValueError("Invalid tariff catalogue")
    for t in data["tariffs"]:
        if not isinstance(t, dict) or t.get("id") != "welsh_water":
            raise ValueError("Unsupported catalogue tariff")
        start, end = date.fromisoformat(t["valid_from"]), date.fromisoformat(t["valid_until"])
        if not 1 <= (end - start).days <= 370:
            raise ValueError("Invalid tariff validity")
        for k in ("water_per_m3", "sewer_per_m3"):
            if not finite(t[k], 0, 20):
                raise ValueError("Invalid usage rate")
        for k in ("water_standing_annual", "sewer_standing_annual", "foul_only_standing_annual"):
            if not finite(t[k], 0, 2000):
                raise ValueError("Invalid standing charge")
        if not finite(t["sewer_return_percent"], 0, 100):
            raise ValueError("Invalid sewer return")
        source = urlparse(t["source"])
        if source.scheme != "https" or source.hostname not in ("corporate.dwrcymru.com", "www.dwrcymru.com"):
            raise ValueError("Invalid official source")
    return data


def select_tariff(catalog, profile, today):
    if profile not in PROFILES or profile == "custom":
        return None
    matches = [t for t in catalog["tariffs"] if date.fromisoformat(t["valid_from"]) <= today <= date.fromisoformat(t["valid_until"])]
    if not matches:
        return None
    t = max(matches, key=lambda v: v["valid_from"])
    water_only = profile == "welsh_water_only"
    sewer_standing = t["foul_only_standing_annual"] if profile == "welsh_foul_only" else t["sewer_standing_annual"]
    return {
        "water_rate": t["water_per_m3"], "sewer_rate": 0 if water_only else t["sewer_per_m3"],
        "annual_standing": t["water_standing_annual"] + (0 if water_only else sewer_standing),
        "return_percent": t["sewer_return_percent"], "valid_until": t["valid_until"],
        "valid_from": t["valid_from"], "source": t["source"],
    }


def complete_daily_records(rows, now, days):
    """Require each expected hourly row; exclude today and the first observed date.

    This detects missing statistic hours, not all short monitoring gaps. Results
    remain estimates, particularly where the physical device was unavailable.
    """
    if not rows:
        return {}
    tz = now.tzinfo
    first_day = min(datetime.fromtimestamp(r["start"], tz).date() for r in rows)
    grouped = {}
    for r in rows:
        start = datetime.fromtimestamp(r["start"], tz)
        day = start.date()
        if day <= first_day or not now.date() - timedelta(days=days) <= day < now.date():
            continue
        if finite(r.get("change")):
            grouped.setdefault(day, {})[r["start"]] = r["change"]
    result = {}
    for day, values in sorted(grouped.items()):
        start = datetime.combine(day, datetime.min.time(), tz)
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tz)
        expected = int((end.timestamp() - start.timestamp()) / 3600)
        expected_starts = {start.timestamp() + h * 3600 for h in range(expected)}
        if set(values) == expected_starts:
            result[day] = sum(values.values())
    return result


def complete_daily_usage(rows, now, days):
    return list(complete_daily_records(rows, now, days).values())


def calculate(tariff, annual_bill, daily_m3, today_m3=None):
    """Annualise observed full days at current rates, not a future-price forecast."""
    result = {"sample_days": len(daily_m3)}
    bill = annual_bill if finite(annual_bill, 0.01) else None
    result["current_annual_bill"] = bill
    if tariff is None:
        return result
    rate = tariff["water_rate"] + tariff["sewer_rate"] * tariff["return_percent"] / 100
    standing = tariff["annual_standing"]
    result.update(water_rate=tariff["water_rate"], sewer_rate=tariff["sewer_rate"],
                  effective_rate=rate, annual_standing=standing)
    if bill is not None and rate > 0:
        result["break_even_daily_litres"] = max(0, bill - standing) / rate / 365 * 1000
    if finite(today_m3):
        result["today_metered_cost"] = today_m3 * rate + standing / 365
    if daily_m3:
        average = sum(daily_m3) / len(daily_m3)
        cost = average * 365 * rate + standing
        result.update(average_daily_litres=average * 1000, projected_annual_m3=average * 365,
                      projected_annual_cost=cost, projected_monthly_cost=cost / 12)
        if bill is not None:
            result["projected_annual_saving"] = bill - cost
        if len(daily_m3) >= 7 and bill is not None:
            result["comparison_result"] = "Metered estimate lower" if cost < bill else "Unmetered bill lower or equal"
    return result
