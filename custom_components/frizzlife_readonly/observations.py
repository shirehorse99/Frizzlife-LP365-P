"""Bounded local observation ledger; gaps never become zero usage or flow."""
from datetime import datetime, timedelta
from .comparison import finite


def day_parts(start, end, tz):
    cursor = start
    while cursor < end:
        local = datetime.fromtimestamp(cursor, tz)
        tomorrow = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), tz).timestamp()
        stop = min(end, tomorrow)
        yield local.date().isoformat(), stop - cursor
        cursor = stop


class ObservationLedger:
    def __init__(self, data=None):
        data = data or {}
        self.days = data.get("days", {})
        self.segments = data.get("segments", [])
        self.last = data.get("last")
        self.started = data.get("started")
        self.last_success = data.get("last_success")
        # Runs are deliberately not restored: downtime must not extend a run.
        self.flow_since = None
        self.flow_threshold = None
        self.pressure_runs = {}
        self.samples = data.get("samples", {})

    def dump(self):
        return {"days": self.days, "segments": self.segments, "last": self.last, "started": self.started,
                "last_success": self.last_success, "samples": self.samples}

    def record(self, now, success, water=None, flow=None, pressure=None, flow_threshold=5, options=None):
        stamp, tz = now.timestamp(), now.tzinfo
        self.started = self.started or stamp
        key = now.date().isoformat()
        d = self.days.setdefault(key, {"attempts": 0, "successes": 0, "covered": 0, "max_gap": 0,
                                      "pressure_count": 0, "pressure_sum": 0})
        d["attempts"] += 1
        d["successes"] += int(success)
        if success:
            self.last_success = stamp
        valid = success and finite(water)
        previous = self.last
        gap = stamp - previous["at"] if previous else None
        if previous and gap is not None and gap > 0:
            start = max(previous["at"], stamp - 94 * 86400)
            covered = valid and previous["valid"] and gap <= 90
            for day, seconds in day_parts(start, stamp, tz):
                bucket = self.days.setdefault(day, {"attempts": 0, "successes": 0, "covered": 0,
                    "max_gap": 0, "pressure_count": 0, "pressure_sum": 0})
                if covered:
                    bucket["covered"] += seconds
                else:
                    bucket["max_gap"] = max(bucket["max_gap"], seconds)
            if covered:
                if self.segments and start <= self.segments[-1][1] + .001:
                    self.segments[-1][1] = max(stamp, self.segments[-1][1])
                else:
                    self.segments.append([start, stamp])
        if success and finite(pressure):
            d["pressure_count"] += 1
            d["pressure_sum"] += pressure
            d["pressure_min"] = min(d.get("pressure_min", pressure), pressure)
            d["pressure_max"] = max(d.get("pressure_max", pressure), pressure)
        if valid:
            samples = self.samples.setdefault(key, {})
            # Keep the latest observation in each five-minute bucket, three days.
            samples[str(int(stamp // 300))] = [stamp, water]
        sample_cutoff = (now.date() - timedelta(days=2)).isoformat()
        self.samples = {k: v for k, v in self.samples.items() if k >= sample_cutoff}
        options = options or {}
        limits = (options.get("pressure_low_bar", 1), options.get("pressure_high_bar", 6))
        for name, active in (("pressure_low", finite(pressure) and pressure < limits[0]),
                             ("pressure_high", finite(pressure) and pressure > limits[1])):
            prior = self.pressure_runs.get(name)
            if not success or not finite(pressure) or not active or not options.get("pressure_alerts_enabled", False):
                self.pressure_runs[name] = None
            elif prior is None or gap is None or gap <= 0 or gap > 90 or prior[1] != limits:
                self.pressure_runs[name] = [stamp, limits]
        flowing = success and finite(flow) and flow >= flow_threshold
        if not flowing:
            self.flow_since = None
        elif self.flow_since is None or gap is None or gap > 90 or self.flow_threshold != flow_threshold:
            self.flow_since = stamp
        self.flow_threshold = flow_threshold
        self.last = {"at": stamp, "success": success, "valid": valid, "flow": flow if success else None, "pressure": pressure if success else None}
        cutoff = stamp - 94 * 86400
        self.segments = [[max(a, cutoff), b] for a, b in self.segments if b > cutoff][-10000:]
        min_day = datetime.fromtimestamp(cutoff, tz).date().isoformat()
        self.days = {k: v for k, v in self.days.items() if k >= min_day}

    def coverage(self, start, end):
        if end <= start:
            return None
        seconds = sum(max(0, min(b, end) - max(a, start)) for a, b in self.segments)
        return min(100, seconds / (end - start) * 100)

    def usable_day(self, day, tz):
        start = datetime.combine(day, datetime.min.time(), tz).timestamp()
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tz).timestamp()
        cursor, max_gap = start, 0
        for a, b in self.segments:
            if b <= start or a >= end:
                continue
            a, b = max(start, a), min(end, b)
            max_gap = max(max_gap, a - cursor)
            cursor = max(cursor, b)
        max_gap = max(max_gap, end - cursor)
        return self.coverage(start, end) >= 99 and max_gap <= 90

    def live(self, now, options):
        stamp = now.timestamp()
        midnight = datetime.combine(now.date(), datetime.min.time(), now.tzinfo)
        age = stamp - self.last["at"] if self.last else None
        healthy = self.last is not None and self.last["success"] and 0 <= age <= 90
        flow = self.last.get("flow") if healthy else None
        run = max(0, stamp - self.flow_since) / 60 if healthy and self.flow_since is not None else 0 if finite(flow) else None
        start_hour, end_hour = int(options.get("night_start_hour", 0)), int(options.get("night_end_hour", 6))
        hour = now.hour
        in_night = (start_hour <= hour < end_hour) if start_hour < end_hour else (hour >= start_hour or hour < end_hour)
        night_minutes = 0 if finite(flow) else None
        if in_night and self.flow_since is not None and healthy:
            night_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            if night_start > now:
                night_start -= timedelta(days=1)
            night_minutes = max(0, stamp - max(self.flow_since, night_start.timestamp())) / 60
        today = self.days.get(now.date().isoformat(), {})
        sustained = (True if run >= options.get("sustained_minutes", 60) else None) if run is not None and self.flow_since is not None else False if run is not None else None
        overnight = (True if night_minutes >= options.get("overnight_minutes", 30) else None) if in_night and self.flow_since is not None and healthy else False if night_minutes is not None else None
        result = {
            "monitoring_online": healthy, "last_attempt_age": age,
            "coverage_24h": self.coverage(stamp - 86400, stamp),
            "coverage_today": self.coverage(midnight.timestamp(), stamp),
            "tracking_hours": (stamp - self.started) / 3600 if self.started else 0,
            "flow_run_minutes": run, "night_flow_minutes": night_minutes,
            "sustained_flow": sustained, "overnight_flow": overnight,
        }
        pressure = self.pressure_runs
        for name in ("pressure_low", "pressure_high"):
            run = pressure.get(name)
            valid_pressure = healthy and finite(self.last.get("pressure")) and options.get("pressure_alerts_enabled", False)
            result[name] = (True if stamp - run[0] >= options.get("pressure_alert_minutes", 5) * 60 else None) if valid_pressure and run else False if valid_pressure else None
        # A matched prior observation is approximate to five minutes. Missing
        # checkpoints stay unavailable; the quality check is applied by analytics.
        yesterday = now.date() - timedelta(days=1)
        previous_time = now.replace(year=yesterday.year, month=yesterday.month, day=yesterday.day)
        candidates = [v for v in self.samples.get(yesterday.isoformat(), {}).values()
                      if 0 <= previous_time.timestamp() - v[0] <= 300]
        if candidates:
            result["yesterday_same_time"] = max(candidates)[1] * 1000
        if today.get("pressure_count"):
            result.update(pressure_min_today=today["pressure_min"], pressure_max_today=today["pressure_max"],
                          pressure_mean_today=today["pressure_sum"] / today["pressure_count"])
        return result
