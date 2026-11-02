"""Observed usage trends and sensitivity scenarios, not leak diagnosis."""
from datetime import datetime, timedelta
from .comparison import finite, complete_daily_records


def daily_records(rows, now):
    return complete_daily_records(rows, now, 93)


def usage_summary(rows, now, ledger, today_m3=None, records=None):
    records = daily_records(rows, now) if records is None else records
    usable = {d: v for d, v in records.items() if ledger.usable_day(d, now.tzinfo)}
    result = {}
    yesterday = now.date() - timedelta(days=1)
    if yesterday in usable:
        result["water_yesterday"] = usable[yesterday] * 1000
    for window in (7, 30, 90):
        values = [v for d, v in usable.items() if now.date() - timedelta(days=window) <= d < now.date()]
        result[f"usable_days_{window}"] = len(values)
        result[f"history_progress_{window}"] = min(100, len(values) / window * 100)
        if values:
            result[f"average_{window}"] = sum(values) / len(values) * 1000
    for name, start in (("week", now.date() - timedelta(days=now.weekday())),
                        ("month", now.date().replace(day=1))):
        changes = [r["change"] for r in rows if finite(r.get("change")) and
                   start <= datetime.fromtimestamp(r["start"], now.tzinfo).date() < now.date()]
        if changes or finite(today_m3):
            result[f"recorded_{name}"] = (sum(changes) + (today_m3 if finite(today_m3) else 0)) * 1000
        start_time = datetime.combine(start, datetime.min.time(), now.tzinfo).timestamp()
        result[f"coverage_{name}"] = ledger.coverage(start_time, now.timestamp())
    count = result["usable_days_90"]
    result["history_confidence"] = ("Collecting: fewer than 7 usable days" if count < 7 else
        "Preliminary: 7–29 usable days" if count < 30 else
        "30–89 usable days; seasonal uncertainty remains" if count < 90 else
        "90 usable days; seasonal uncertainty remains")
    return result, usable


def scenarios(tariff, average_litres, bill, options):
    if tariff is None or not finite(average_litres):
        return {}
    usage_change = options.get("scenario_usage_percent", 20) / 100
    price_change = options.get("scenario_tariff_percent", 10) / 100
    volume = average_litres / 1000 * 365
    variable = volume * (tariff["water_rate"] + tariff["sewer_rate"] * tariff["return_percent"] / 100)
    standing = tariff["annual_standing"]
    result = {"scenario_lower_usage": standing + variable * max(0, 1 - usage_change),
              "scenario_higher_usage": standing + variable * (1 + usage_change),
              "scenario_tariff_rise": (standing + variable) * (1 + price_change)}
    if finite(bill, .01):
        result["scenario_rise_saving"] = bill - result["scenario_tariff_rise"]
    return result
