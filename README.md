# FrizzLife LP365-P — Home Assistant water monitor

Trial version 0.4.0, targeting with Home Assistant 2026.10.4 and one LP365-P using local protocol 3.5. Local authentication, live entities, the dashboard tabs and Energy water/flow source selection were verified. Multi-device and other firmware support remain untested.

Provides native readings and editable HA settings with nine dashboard tabs: Overview, Usage, Diagnostics, Meter comparison, Quality, Leak protection, Scenarios, Settings and Manual controls. Optional manual valve commands are disabled by default. No protection-setting writes, mode changes or resets are provided. A separate notification-test action sends only messages. Polls every 30 seconds using local Tuya status queries. Phone apps or another local integration may compete for the device's single connection.

## Installation

Copy `custom_components/frizzlife_readonly` into HA's `custom_components` directory and restart Home Assistant. Under Settings → Devices & services, add **FrizzLife Water Monitor (read only)**. Configure the current IP, current Device ID, local key and protocol (3.5 on the tested unit). The key is private and stored in HA's config entry; protect backups. Re-pairing changes the device identity/key.

Only enable verified volume readings after checking the app. The verified unit reports DP 103 as today's usage in tenths of a litre in metric mode, DP 105 as flow in thousandths of L/h, and DP 102 as the unit selection. US gallon values are normalised to metric. DP 15 is tenths of a psi on the tested firmware: use pressure multiplier **0.1**. Tuya's cloud schema incorrectly labels that pressure MPa; it must not be used for conversion. The reported temperature is excluded because this is the pressure model and its temperature datapoint appears to be a placeholder.

## Energy dashboard

Select the integration's **Water used today** sensor under Settings → Dashboards → Energy → Water consumption. It uses `device_class: water`, `state_class: total_increasing` and `m³`, so Recorder can accumulate water use across the daily reset. It is a **daily device counter**, not a fabricated lifetime meter. Wait for Recorder's first statistics cycle if it is not immediately selectable. Keep Recorder enabled for this entity. On HA versions that offer a water flow rate selector, also select **Water flow**.

Do not add another derivative alongside this source, as that double-counts water. Earlier FrizzLife/Smart Life cloud history is not imported. The device's configured midnight determines its reset; no reset commands are sent. Changes to the device's unit setting may introduce rounding, so validate statistics after changing that setting in the phone app. Prefer leaving the selected units unchanged.

## MVHR-style dashboard

1. Add `/frizzlife_readonly/dashboard.js?v=0.4.0-2` as a **JavaScript module** under Settings → Dashboards → Resources (advanced mode may be required).
2. Create a new blank dashboard and take control of it.
3. In its raw configuration editor enter:

```yaml
strategy:
  type: custom:frizzlife-readonly
```

The strategy discovers entities through HA's registries, so entity renames work and no personal entity IDs appear in the layout. Sensor/binary sensor entities and the integration’s own local settings are selected; unrelated control entities are excluded. No frontend framework or extra card plugins are required.

## Extra read-only diagnostics

Version 0.1.2 adds seven fault flags decoded from the vendor bitmap (power, empty pipe, backflow, over-range, temperature, hardware and stuck valve), configured protection modes, low-flow protection status, alarm-time raw values and flow-threshold codes. Leak/warning event duration and volume, plus test remaining time, are exposed as raw diagnostics with no assumed units or active-event meaning. Some values may remain from earlier events or inactive settings. These are grouped on the Diagnostics tab. Raw device configuration remains read-only; local HA settings have their own Settings tab. A reported temperature fault flag does not establish a working temperature sensor on the pressure model.

## Verification and limitations

Run `.venv/bin/python -m unittest discover -s tests -v`. The tests cover verified counter conversion, unit switching, invalid/missing values, daily reset handling, individual fault bits, extra diagnostic validation, command rejection and connection cleanup. Also run `node tests/test_dashboard.cjs` for registry discovery and graph configuration checks. A live HA trial verified setup after restart, repeated polling, pressure in psi, flow in L/h, consumption in litres, the rendered Overview/Usage/Diagnostics tabs, and Energy selection. History graphs need time to accumulate. HACS/hassfest validation is not claimed as passed.

Normal polling uses only status queries (including required session authentication). Manual valve writes, when explicitly enabled and confirmed, use a separate transport restricted to boolean DP1. It rejects TinyTuya's device22 control-opcode fallback rather than silently sending it. Missing datapoints are unavailable; unsuccessful polls make entities unavailable. A successful poll means the device answered, not that its physical sensors sampled at that instant. Fault bitmap zero means only that the monitor reported no fault flags.

## Local development records

Local `private/` contains credentials and private evidence, is ignored by Git, and must never be packaged or published. The read-status utility prompts for a key or reads a private key file; do not place a key on a command line.

Sources: [FrizzLife support](https://www.frizzlife.com/pages/lp365-support), [Home Assistant water in Energy](https://www.home-assistant.io/docs/energy/water/), [TinyTuya](https://github.com/jasonacox/tinytuya).

## Community cross-check

[LP365 community discussion](https://community.home-assistant.io/t/frizzlife-smart-water-monitor/875335?page=2) confirms pressure /10 psi and today usage /10 L, and reports incorrect cloud naming for DP104. DP104 is therefore exposed only as a raw diagnostic, with no unit or claimed meaning. Live flow is /1000 L/h, confirmed by the user’s Smart Life display. Earlier example YAML in the thread misclassifies volume as flow rate; this integration uses water / total_increasing for Energy.

## Metered versus unmetered comparison

In the integration’s options, enable **Water meter cost comparison**, select a region/supplier tariff and enter your current annual unmetered bill when known (0 means unknown). The presets currently cover standard Welsh Water household water and sewerage, an approved surface-water rebate, and water only. Other regions/suppliers use custom manual rates and an expiry date; there is no claim of automatic national supplier coverage.

Sensors expose the tariff, annual standing charge, today’s indicative metered cost, full days included, average daily usage, annualised volume, estimated annual/monthly metered cost, annual saving, and break-even litres/day. The first recorded date, today, and dates missing expected hourly Recorder statistics are excluded. DST days use their actual 23/25 hours. Estimates begin with one complete recorded day; the comparison result needs seven. A positive saving means the metered estimate is lower. Unknown bills leave saving/break-even unavailable. Recorder and verified volume readings are required. Short monitoring gaps may still affect estimates; the monitor must measure the whole household supply. Seasonal use needs a representative longer sample.

These are indicative current-tariff projections over 365 days, not supplier quotes or forecasts of future tariffs. The default Welsh Water sewer-return factor is 95%; very low-volume billing, social tariffs, discounts, and individually approved allowances can differ. Changing the return factor affects only the estimate. Comparison entities are not billing controls or Energy cost configuration.

Automatic updates check the **maintained JSON catalogue in this repository** daily using a public GET, and cache valid rates locally. This is not an official live supplier API or automatic PDF scraping: catalogue maintainers must publish verified tariff changes. No usage or bill amounts are uploaded. Only dated, bounded rates with an allowed official source are accepted. Current valid cached/bundled rates can survive a failed check; expired tariffs produce no monetary estimates. Custom supplier rates are manual. Rates and update status are visible on the dashboard.

Welsh Water 2026–27 tariff source: [household scheme of charges](https://corporate.dwrcymru.com/-/media/project/files/page-documents/corporate/library/our-charges/scheme-of-charges/scheme-of-charges-2026-2027.ashx). Calculation is cross-checked against the supplier’s [52 m³/year metered example](https://www.dwrcymru.com/en/help-advice/water-meters/switching-to-a-water-meter).

Pressure is exposed simultaneously in psi and bar, with two live dashboard rows. Version 0.2.1 also uses serialisable standard numeric form validators, with finite-value checks on submission.

## Trends, observation quality and pressure summaries

Version 0.3.0 adds recorded week/month totals, yesterday from a usable day, rolling 7/30/90-day averages with sample counts, history-target progress gauges and observed coverage. Current-day usage comes from the device daily counter; previous dates use recorded hourly changes and can be incomplete. Averages and cost comparisons require all expected hourly statistics, at least 99% observed water-counter coverage, and no observation gap over 90 seconds. DST dates use their actual duration. Coverage before observation tracking began is unknown and counts as unobserved, not as proof of a device fault or zero consumption. Old history is retained but cannot be certified retrospectively. Coverage and pressure observations persist locally, with periodic saves; a crash can lose the latest minute.

Daily pressure minimum, maximum and arithmetic mean use successful observed samples in bar, and may describe only part of the day. Flow observations restart after a gap or reload; unknown data never becomes a leak all-clear. Default patterns are >=5 L/h for 60 minutes, and 30 minutes during the local 00:00–06:00 night window. High daily use requires 7 usable days, exceeds twice the 30-day observed average and exceeds 500 L. These are adjustable observation rules, not verified leak diagnoses or device shutoff limits.

Cost sensitivity defaults are 20% less/more usage and a 10% increase in both metered standing and volumetric charges, keeping the unmetered baseline unchanged. Percentages are editable under observation/scenario options. No future price increase is predicted.

## Notifications and shutoff review

Enable HA notifications and optionally select a `mobile_app_…` phone destination in integration options. Messages cover device leak warnings/alarms, valve-closed and protection-disabled states, reported fault bits, a monitoring outage (default 5 minutes) and the configured usage patterns. Notifications are emitted on transitions, not every poll. Missing data does not clear an alert. Recovery means a reported condition/rule is no longer active, not that a leak has been physically resolved. HA persistent messages use stable IDs; the last-message sensor keeps ten recent messages. Phone-service acceptance does not prove phone receipt. Failed/unavailable phone sends are queued locally and retried, with a maximum 24-hour age and ten pending messages. HA and network availability are required.

The notification-test action is `frizzlife_readonly.test_notifications`, targeting one loaded integration entry. It sends a clearly labelled test through the selected HA/phone destinations and sends no device command. Existing entries can load quality/alert entities even when the device is offline at HA startup.

Device-side Protect/Unprotect and automatic shutoff remain independent of the HA observation rules. [The shutoff review](docs/leak-protection.md) describes the manufacturer guidance and a supervised next step. This project does not change device protection, reset alarms or run its leak test. Optional manual valve actions are described below.

Version 0.3.0 validation: 23 Python tests, dashboard tests and compilation pass. Live HA 2026.10.4 loaded 94 entities and all seven views; observed pressure summaries, coverage, current-day/week/month totals, scenario assumptions and notification settings were verified. A notification-only test created an HA message and was accepted by the selected mobile-app service. That does not by itself prove receipt on the handset. No valve/protection command or physical closure test was performed.


## Version 0.4.0 dashboard settings and manual control

Usage adds hourly consumption, target progress/remaining litres, yesterday at approximately the same time (five-minute checkpoints), and recorded night consumption. A target of zero selects current tariff/bill break-even; a positive value is a manual litre target. A negative remaining value means over target. The gauge caps visually at 100%; the sensor retains the actual percentage. Same-time history starts when 0.4.0 is installed and requires a usable yesterday. Night consumption uses completed hourly Recorder changes on the current local calendar date within the configured night hours; the current unfinished hour is excluded and missing hours can understate use.

Settings exposes native numbers, switches and selectors for notification destination, flow/night/outage observations, pressure limits and duration, cost assumptions, comparison window and daily target. Changes remain local HA options and preserve observation history. Supplier/custom tariffs remain in integration options. Pressure alerts are off by default, with editable initial limits 1–6 bar lasting five minutes; these are observation defaults, not manufacturer limits or advice about suitable plumbing pressure. Missing observations, restart or a gap over 90 seconds restart pressure runs. They never operate the valve.

Leak protection includes recent messages and a 30-day supervised-test reminder. “Record completed supervised test” records the user's assertion that a manufacturer test has already been completed, actual supply interruption checked, supply restored and protection re-enabled. It sends no valve/test commands and is not independent evidence of mechanical operation.

Manual controls are opt-in. Enabling “Allow manual water valve commands” makes confirmed Open/Close actions available; it does not move the valve. `frizzlife_readonly.set_manual_valve` requires a loaded entry, this opt-in, a current reported valve position, `state: Open` or `Closed`, and `confirmed: true`. It sends one boolean DP1 write through a separate restricted transport, serialised with polling, and checks a subsequent reported state. No automatic control retries or automatic HA shutoff rules are installed. A timeout can mean the command reached the device but its reply was lost: inspect the monitor before trying again. Closing interrupts supply; opening may restore flow into an unresolved leak. Reported success does not prove physical closure. Protection/mode/threshold writes remain excluded.

Software validation covers pressure run duration/gaps/restart, checkpoint retention, manual opt-in/confirmation/current-state guards, DP1-only writes and dashboard action confirmations. Physical valve operation requires a supervised test at the installation and has not been verified by this project.
