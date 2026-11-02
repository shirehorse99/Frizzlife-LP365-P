"""Pure datapoint decoding; missing/invalid measurements never become zero."""
import math


def number(dps, dp):
    value = dps.get(str(dp))
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return value


def decode(dps, key, pressure_factor=None):
    if key == "pressure_raw":
        return number(dps, 15)
    if key == "reported_104":
        return number(dps, 104)
    if key == "pressure":
        value = number(dps, 15)
        return value * pressure_factor if value is not None and pressure_factor else None
    if key in ("water_today", "flow"):
        units = dps.get("102")
        if units not in ("metric_unit", "us_units"):
            return None
        dp, divisor = {"water_today": (103, 10), "flow": (105, 1000)}[key]
        value = number(dps, dp)
        if value is None:
            return None
        # Normalise US gallons to litres; Energy uses cubic metres for volume.
        litres = value / divisor * (3.785411784 if units == "us_units" else 1)
        return litres if key == "flow" else litres / 1000
    if key == "valve_position":
        value = dps.get("1")
        return ("Open" if value else "Closed") if type(value) is bool else None
    if key == "protection":
        value = dps.get("101")
        return ("Enabled" if value else "Disabled") if type(value) is bool else None
    if key == "measurement_units":
        return dps.get("102") if dps.get("102") in ("metric_unit", "us_units") else None
    if key == "faults":
        return number(dps, 24)
    if key in ("leak_warning", "leak_alarm"):
        value = dps.get({"leak_warning": "106", "leak_alarm": "107"}[key])
        return value if type(value) is bool else None
    return None
