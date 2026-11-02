# FrizzLife LP365-P — read-only Home Assistant integration

Trial version 0.1.2, tested with Home Assistant 2026.10.4 and one LP365-P using local protocol 3.5. Local authentication, live entities, the three dashboard tabs and Energy water/flow source selection were verified. Multi-device and other firmware support remain untested.

Provides native sensor and binary sensor entities, plus a reusable three-tab Lovelace dashboard: Overview, Usage and Diagnostics. No control entities, services, valve commands, protection changes or resets. Polls every 30 seconds using local Tuya status queries. Phone apps or another local integration may compete for the device's single connection.

## Installation

Copy `custom_components/frizzlife_readonly` into HA's `custom_components` directory and restart Home Assistant. Under Settings → Devices & services, add **FrizzLife Water Monitor (read only)**. Configure the current IP, current Device ID, local key and protocol (3.5 on the tested unit). The key is private and stored in HA's config entry; protect backups. Re-pairing changes the device identity/key.

Only enable verified volume readings after checking the app. The verified unit reports DP 103 as today's usage in tenths of a litre in metric mode, DP 105 as flow in thousandths of L/h, and DP 102 as the unit selection. US gallon values are normalised to metric. DP 15 is tenths of a psi on the tested firmware: use pressure multiplier **0.1**. Tuya's cloud schema incorrectly labels that pressure MPa; it must not be used for conversion. The reported temperature is excluded because this is the pressure model and its temperature datapoint appears to be a placeholder.

## Energy dashboard

Select the integration's **Water used today** sensor under Settings → Dashboards → Energy → Water consumption. It uses `device_class: water`, `state_class: total_increasing` and `m³`, so Recorder can accumulate water use across the daily reset. It is a **daily device counter**, not a fabricated lifetime meter. Wait for Recorder's first statistics cycle if it is not immediately selectable. Keep Recorder enabled for this entity. On HA versions that offer a water flow rate selector, also select **Water flow**.

Do not add another derivative alongside this source, as that double-counts water. Earlier FrizzLife/Smart Life cloud history is not imported. The device's configured midnight determines its reset; no reset commands are sent. Changes to the device's unit setting may introduce rounding, so validate statistics after changing that setting in the phone app. Prefer leaving the selected units unchanged.

## MVHR-style dashboard

1. Add `/frizzlife_readonly/dashboard.js` as a **JavaScript module** under Settings → Dashboards → Resources (advanced mode may be required).
2. Create a new blank dashboard and take control of it.
3. In its raw configuration editor enter:

```yaml
strategy:
  type: custom:frizzlife-readonly
```

The strategy discovers entities through HA's registries, so entity renames work and no personal entity IDs appear in the layout. Only sensor/binary sensor domains are selected. No frontend framework or extra card plugins are required.

## Extra read-only diagnostics

Version 0.1.2 adds seven fault flags decoded from the vendor bitmap (power, empty pipe, backflow, over-range, temperature, hardware and stuck valve), configured protection modes, low-flow protection status, alarm-time raw values and flow-threshold codes. Leak/warning event duration and volume, plus test remaining time, are exposed as raw diagnostics with no assumed units or active-event meaning. Some values may remain from earlier events or inactive settings. These are grouped on the Diagnostics tab. No settings can be changed through the integration. A reported temperature fault flag does not establish a working temperature sensor on the pressure model.

## Verification and limitations

Run `.venv/bin/python -m unittest discover -s tests -v`. The tests cover verified counter conversion, unit switching, invalid/missing values, daily reset handling, individual fault bits, extra diagnostic validation, command rejection and connection cleanup. Also run `node tests/test_dashboard.cjs` for registry discovery and graph configuration checks. A live HA trial verified setup after restart, repeated polling, pressure in psi, flow in L/h, consumption in litres, the rendered Overview/Usage/Diagnostics tabs, and Energy selection. History graphs need time to accumulate. HACS/hassfest validation is not claimed as passed.

The integration uses only status queries (including required session authentication). It rejects TinyTuya's device22 control-opcode fallback rather than silently sending it. Missing datapoints are unavailable; unsuccessful polls make entities unavailable. A successful poll means the device answered, not that its physical sensors sampled at that instant. Fault bitmap zero means only that the monitor reported no fault flags.

## Local development records

Local `private/` contains credentials and private evidence, is ignored by Git, and must never be packaged or published. The read-status utility prompts for a key or reads a private key file; do not place a key on a command line.

Sources: [FrizzLife support](https://www.frizzlife.com/pages/lp365-support), [Home Assistant water in Energy](https://www.home-assistant.io/docs/energy/water/), [TinyTuya](https://github.com/jasonacox/tinytuya).

## Community cross-check

[LP365 community discussion](https://community.home-assistant.io/t/frizzlife-smart-water-monitor/875335?page=2) confirms pressure /10 psi and today usage /10 L, and reports incorrect cloud naming for DP104. DP104 is therefore exposed only as a raw diagnostic, with no unit or claimed meaning. Live flow is /1000 L/h, confirmed by the user’s Smart Life display. Earlier example YAML in the thread misclassifies volume as flow rate; this integration uses water / total_increasing for Energy.
