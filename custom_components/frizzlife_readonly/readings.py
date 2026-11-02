"""Pure datapoint decoding; missing/invalid measurements never become zero."""
import math

FAULT_BITS = {
    "fault_power": 0, "fault_empty_pipe": 1, "fault_backflow": 2,
    "fault_overrange": 3, "fault_temperature": 4, "fault_hardware": 5,
    "fault_valve_stuck": 6,
}
RAW_DIAGNOSTICS = {
    "mode4_time_raw": 112, "mode5_time_raw": 113, "mode6_time_raw": 114,
    "leak_duration_raw": 121, "leak_volume_raw": 122,
    "warning_duration_raw": 123, "warning_volume_raw": 124,
    "test_remaining_raw": 127,
}


def number(dps, dp):
    value = dps.get(str(dp))
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return value


def decode(dps, key, pressure_factor=None):
    if key in FAULT_BITS:
        value = dps.get("24")
        return bool(value & (1 << FAULT_BITS[key])) if type(value) is int and value >= 0 else None
    if key in RAW_DIAGNOSTICS:
        return number(dps, RAW_DIAGNOSTICS[key])
    if key == "low_flow_enabled":
        value = dps.get("118")
        return value if type(value) is bool else None
    if key == "mode_group":
        value = dps.get("109")
        return {"AUTO": "Automatic", "ADVANCED_SETTING": "Advanced settings"}.get(value) if isinstance(value, str) else None
    if key in ("smart_mode", "pro_mode"):
        dp, allowed = ("110", ("mode1", "mode2", "mode3")) if key == "smart_mode" else ("111", ("mode4", "mode5", "mode6"))
        value = dps.get(dp)
        return "Mode " + value[4:] if isinstance(value, str) and value in allowed else None
    if key in ("mode4_flow_code", "mode5_flow_code", "mode6_flow_code", "low_flow_code"):
        dp = {"mode4_flow_code": "115", "mode5_flow_code": "116", "mode6_flow_code": "117", "low_flow_code": "119"}[key]
        value = dps.get(dp)
        maximum = 9 if key == "low_flow_code" else 26
        return value if isinstance(value, str) and value in tuple(str(i) for i in range(maximum + 1)) else None
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
