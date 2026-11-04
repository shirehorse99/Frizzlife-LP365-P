"""Notification transitions only. This module never commands the water valve."""

EVENTS = {
    "pressure_low": ("Sustained low water pressure", "Pressure has stayed below your configured bar limit for the configured duration. This is an observation and does not operate the valve."),
    "pressure_high": ("Sustained high water pressure", "Pressure has stayed above your configured bar limit for the configured duration. Check the pressure history; this does not operate the valve."),
    "device_leak_alarm": ("Device leak alarm", "The monitor reports a leak alarm. Check the property and the reported valve position; closure has not been physically verified."),
    "device_leak_warning": ("Device leak warning", "The monitor reports a leak warning. Investigate water use and check its app."),
    "protection_disabled": ("Leak protection disabled", "The monitor reports that its own leak protection is disabled. Check its app or panel."),
    "valve_closed": ("Water valve reported closed", "The monitor reports its valve closed. This message does not establish why it closed or verify mechanical closure."),
    "monitor_offline": ("Water monitoring unavailable", "Home Assistant has not received a successful local reading within the configured outage period. Device-side protection may still operate; HA cannot verify it while offline."),
    "sustained_flow": ("Sustained water use", "Flow has remained above the configured observation threshold for the configured duration. This may be normal use and is not a confirmed leak."),
    "overnight_flow": ("Sustained overnight water use", "Flow has continued during the configured night window. Check for expected appliances or taps; this is not a confirmed leak."),
    "high_daily_use": ("Unusually high water use today", "Today's device counter exceeds the configured threshold based on usable recorded days. Check for expected extra use; this is not a confirmed leak."),
    "device_fault": ("Water monitor fault reported", "The monitor reports one or more fault bits. Review the fault indicators and manufacturer guidance."),
}


class AlertGate:
    def __init__(self, states=None):
        self.states = states or {}

    def evaluate(self, values):
        events = []
        for key, (title, message) in EVENTS.items():
            value = values.get(key)
            if type(value) is not bool:
                continue  # Missing data is not an all-clear.
            previous = self.states.get(key)
            if value and previous is not True:
                events.append((key, title, message))
            elif not value and previous is True:
                events.append((key, title + " — no longer active", "This reported condition or observation rule is no longer active. A night-flow rule can end when the night window ends. This does not confirm that a leak has been resolved or verify physical safety."))
            self.states[key] = value
        return events
