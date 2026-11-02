"""Separate tariff/statistics refresh; financial data never leaves Home Assistant."""
from datetime import timedelta
import json
import logging
from pathlib import Path

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .comparison import calculate, complete_daily_usage, select_tariff, validate_catalog
from .const import DOMAIN
from .readings import decode

CATALOG_URL = "https://raw.githubusercontent.com/shirehorse99/Frizzlife-LP365-P/main/custom_components/frizzlife_readonly/tariffs.json"


class ComparisonCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, monitor):
        super().__init__(hass, logging.getLogger(__name__), name=f"{DOMAIN}_comparison",
                         update_interval=timedelta(hours=1), config_entry=monitor.entry)
        self.monitor = monitor
        self.entry = monitor.entry
        self.catalog = None
        self.tariff = None
        self.days = []
        self.next_check = None
        self.last_checked = None
        self.check_status = "Bundled tariff; not checked"
        self.stats_status = "Waiting for full days"
        self.store = Store(hass, 1, f"{DOMAIN}_tariffs_{self.entry.entry_id}")

    async def _async_update_data(self):
        if not self.entry.options.get("comparison_enabled", False):
            return {"comparison_status": "Disabled — configure integration options"}
        if not self.entry.data.get("verified_volume", False):
            return {"comparison_status": "Verified volume readings required"}
        now = dt_util.now()
        if self.catalog is None:
            bundled = await self.hass.async_add_executor_job(
                lambda: json.loads((Path(__file__).parent / "tariffs.json").read_text()))
            self.catalog = validate_catalog(bundled)
            cached = await self.store.async_load()
            if cached:
                try:
                    self.catalog = validate_catalog(cached["catalog"])
                    self.last_checked = dt_util.parse_datetime(cached.get("last_checked", ""))
                    self.check_status = "Cached catalogue"
                except (ValueError, TypeError, KeyError):
                    pass
        if self.entry.options.get("auto_tariffs", True) and (self.next_check is None or now >= self.next_check):
            self.next_check = now + timedelta(days=1)
            try:
                async with async_get_clientsession(self.hass).get(CATALOG_URL, timeout=15) as response:
                    response.raise_for_status()
                    raw = bytearray()
                    async for chunk in response.content.iter_chunked(16384):
                        raw.extend(chunk)
                        if len(raw) > 262144:
                            raise ValueError("Catalogue too large")
                    remote = validate_catalog(json.loads(raw))
                # Do not discard a still-valid bundled/cached tariff when a new
                # catalogue omits it (for example during an April transition).
                by_dates = {(t["id"], t["valid_from"]): t for t in self.catalog["tariffs"]}
                by_dates.update({(t["id"], t["valid_from"]): t for t in remote["tariffs"]})
                self.catalog = {"schema_version": 1, "tariffs": list(by_dates.values())}
                self.last_checked = dt_util.utcnow()
                self.check_status = "Catalogue checked successfully"
                await self.store.async_save({"catalog": self.catalog, "last_checked": self.last_checked.isoformat()})
            except Exception:
                self.check_status = "Update failed — using dated cached/bundled rates"
        elif not self.entry.options.get("auto_tariffs", True):
            self.check_status = "Automatic catalogue checks disabled"

        options = self.entry.options
        if options.get("tariff_profile", "welsh_standard") == "custom":
            until = options.get("custom_valid_until", "")
            try:
                from datetime import date
                valid = date.fromisoformat(until) >= now.date()
            except (TypeError, ValueError):
                valid = False
            self.tariff = {
                "water_rate": options.get("custom_water_rate", 0),
                "sewer_rate": options.get("custom_sewer_rate", 0),
                "annual_standing": options.get("custom_standing", 0),
                "return_percent": options.get("sewer_return_percent", 95),
                "valid_until": until, "source": "User-entered tariff",
            } if valid else None
        else:
            self.tariff = select_tariff(self.catalog, options.get("tariff_profile", "welsh_standard"), now.date())
            if self.tariff:
                self.tariff["return_percent"] = options.get("sewer_return_percent", self.tariff["return_percent"])
        self.days = []
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{self.entry.data['device_id']}_water_today")
        if entity_id and "recorder" in self.hass.config.components:
            try:
                midnight = dt_util.start_of_local_day(now)
                window = options.get("comparison_days", 30)
                rows = await get_instance(self.hass).async_add_executor_job(
                    statistics_during_period, self.hass, midnight - timedelta(days=window + 2),
                    midnight, {entity_id}, "hour", {"volume": "m³"}, {"change"})
                self.days = complete_daily_usage(rows.get(entity_id, []), now, window)
                self.stats_status = "Recorded full hourly days" if self.days else "Waiting for full days"
            except Exception:
                self.stats_status = "Recorder statistics unavailable"
        else:
            self.stats_status = "Verified volume sensor and Recorder required"
        return self._values()

    def _values(self):
        options = self.entry.options
        today = decode(self.monitor.data or {}, "water_today") if self.monitor.last_update_success else None
        values = calculate(self.tariff, options.get("annual_unmetered_bill", 0), self.days, today)
        values.update(tariff_status=self.check_status if self.tariff else "No valid dated tariff — check options/expiry",
                      tariff_last_checked=self.last_checked)
        if self.tariff:
            values["tariff_valid_until"] = self.tariff["valid_until"]
        if self.tariff is None:
            status = "No valid dated tariff — estimates unavailable"
        elif self.stats_status != "Recorded full hourly days":
            status = self.stats_status
        elif len(self.days) < 7:
            status = "Preliminary — fewer than 7 full days"
        elif not options.get("annual_unmetered_bill", 0):
            status = "Enter annual unmetered bill to compare"
        else:
            status = "Indicative comparison — seasonal use may differ"
        values["comparison_status"] = status
        return values

    def handle_monitor_update(self):
        if self.entry.options.get("comparison_enabled", False) and self.entry.data.get("verified_volume", False) and self.data is not None:
            self.async_set_updated_data(self._values())
