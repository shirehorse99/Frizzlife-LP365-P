"""Bounded local status queries. Never generate device control commands."""
import logging
import tinytuya
from tinytuya.core import command_types as commands


class ReadOnlyDevice(tinytuya.Device):
    def generate_payload(self, command, *args, **kwargs):
        if command not in (commands.DP_QUERY, commands.DP_QUERY_NEW):
            raise ValueError("Only status query commands are permitted")
        payload = super().generate_payload(command, *args, **kwargs)
        if payload.cmd not in (commands.DP_QUERY, commands.DP_QUERY_NEW):
            raise ValueError("Unsupported control-opcode query fallback")
        return payload


def read_status(config):
    # TinyTuya debug messages can contain local keys. Do not enable its logger.
    logging.getLogger("tinytuya").disabled = True
    device = ReadOnlyDevice(config["device_id"], config["host"], config["local_key"],
                            version=float(config.get("protocol", "3.5")))
    device.set_socketTimeout(5)
    device.set_socketRetryLimit(1)
    device.set_retry(False)
    try:
        data = device.status()
        if not isinstance(data, dict) or not isinstance(data.get("dps"), dict):
            raise ValueError("No valid status response")
        return data["dps"]
    finally:
        device.close()
