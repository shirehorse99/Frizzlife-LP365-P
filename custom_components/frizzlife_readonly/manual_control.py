"""Explicit manual valve writes, separate from the read-only poll transport."""
import logging
import tinytuya
from tinytuya.core import command_types as commands


class ManualValveDevice(tinytuya.Device):
    def generate_payload(self, command, data=None, *args, **kwargs):
        if command != commands.CONTROL or not isinstance(data, dict) or set(data) != {"1"} or type(data["1"]) is not bool or args or any(v is not None for v in kwargs.values()):
            raise ValueError("Only a boolean DP1 manual valve command is permitted")
        return super().generate_payload(command, data)


def set_manual_valve(config, opened):
    if type(opened) is not bool:
        raise ValueError("Boolean valve state required")
    logging.getLogger("tinytuya").disabled = True
    device = ManualValveDevice(config["device_id"], config["host"], config["local_key"],
                               version=float(config.get("protocol", "3.5")))
    device.set_socketTimeout(5)
    device.set_socketRetryLimit(1)
    device.set_retry(False)
    try:
        response = device.set_value("1", opened)
        if isinstance(response, dict) and ("Error" in response or "Err" in response):
            raise ValueError("Device rejected the valve command")
    finally:
        device.close()


def validate_manual_request(enabled, confirmed, online, current, desired):
    """Return whether a write is needed, or reject before opening a socket."""
    if enabled is not True or confirmed is not True:
        raise ValueError("Enable manual valve commands and explicitly confirm this action first")
    if online is not True or current not in ("Open", "Closed") or desired not in ("Open", "Closed"):
        raise ValueError("A current reported valve position and supported target are required")
    return current != desired
