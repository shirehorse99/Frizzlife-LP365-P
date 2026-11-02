"""One local status request, without device-setting commands or key logging."""
import argparse
import getpass
import json
import logging
import os
from pathlib import Path

import tinytuya
from tinytuya.core import command_types as commands


class ReadOnlyDevice(tinytuya.Device):
    """Reject control opcodes, including the library's device22 query fallback."""

    def generate_payload(self, command, *args, **kwargs):
        if command not in (commands.DP_QUERY, commands.DP_QUERY_NEW):
            raise ValueError("Only status query commands are permitted")
        payload = super().generate_payload(command, *args, **kwargs)
        if payload.cmd not in (commands.DP_QUERY, commands.DP_QUERY_NEW):
            raise ValueError("Device requires a query fallback outside the read-only allowlist")
        return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--version", required=True, choices=["3.3", "3.4", "3.5"])
    parser.add_argument("--key-file", type=Path, help="Plain text key file; otherwise prompt privately")
    parser.add_argument("--output", type=Path, default=Path("private/status.json"))
    args = parser.parse_args()
    key = args.key_file.read_text().strip() if args.key_file else getpass.getpass("Tuya local key: ")
    if len(key.encode("utf-8")) != 16:
        parser.error("A local key must be 16 bytes. A Virtual ID is a different value.")
    # TinyTuya debug logs can include keys, so disable library logging here.
    logging.getLogger("tinytuya").disabled = True
    device = ReadOnlyDevice(args.device_id, args.host, key, version=float(args.version))
    device.set_socketTimeout(5)
    # TinyTuya interprets this as total connection attempts, not extra retries.
    device.set_socketRetryLimit(1)
    device.set_retry(False)
    try:
        result = device.status()
        if not isinstance(result, dict) or not isinstance(result.get("dps"), dict):
            raise ValueError("No valid datapoints returned; check key and protocol version")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Store only datapoints, never connection credentials or protocol errors.
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as handle:
            json.dump({"dps": result["dps"]}, handle, indent=2)
        os.chmod(args.output, 0o600)
        print(f"Saved {len(result['dps'])} datapoints to {args.output}")
    except (ValueError, OSError):
        parser.exit(1, "Status request failed; no settings commands were sent.\n")
    finally:
        device.close()


if __name__ == "__main__":
    main()
