"""Opt-in HA and mobile-app messages. No water control actions."""
import asyncio
from homeassistant.helpers.storage import Store
from homeassistant.components import persistent_notification
from homeassistant.util import dt as dt_util
from .alerts import AlertGate
from .const import DOMAIN


class NotificationManager:
    def __init__(self, hass, monitor):
        self.hass, self.monitor, self.entry = hass, monitor, monitor.entry
        self.store = Store(hass, 1, f"{DOMAIN}_alerts_{self.entry.entry_id}")
        self.gate, self.history = AlertGate(), []
        self.delivery_status = "Not sent"
        self.lock = asyncio.Lock()
        self.task = None
        self.pending = []

    async def async_load(self):
        saved = await self.store.async_load() or {}
        self.gate = AlertGate(saved.get("states"))
        self.history = saved.get("history", [])[-10:]
        self.delivery_status = saved.get("delivery", "Not sent")
        self.pending = saved.get("pending", [])[-10:]

    def handle_update(self):
        if not self.entry.options.get("notifications_enabled", False):
            return
        if self.task is None or self.task.done():
            self.task = self.entry.async_create_background_task(self.hass, self.async_evaluate(), "FrizzLife notifications")

    async def async_evaluate(self):
        async with self.lock:
            values = self.monitor.analytics.data or {}
            events = self.gate.evaluate(values)
            for key, title, message in events:
                await self.async_send(key, title, message)
            changed = await self.async_retry_phone()
            if events or changed:
                await self.store.async_save({"states": self.gate.states, "history": self.history,
                                             "delivery": self.delivery_status, "pending": self.pending})
                self.monitor.analytics.async_update_listeners()

    async def async_send(self, key, title, message):
        title = "FrizzLife — " + title
        message += "\nObserved: " + dt_util.now().isoformat(timespec="seconds")
        persistent_notification.async_create(self.hass, message, title,
            notification_id=f"{DOMAIN}_{self.entry.entry_id}_{key}")
        target = self.entry.options.get("phone_notify_service", "none")
        self.delivery_status = "Home Assistant notification created"
        if target != "none":
            if target.startswith("mobile_app_") and self.hass.services.has_service("notify", target):
                try:
                    await self.hass.services.async_call("notify", target,
                        {"title": title, "message": message}, blocking=True)
                    self.delivery_status = "HA notification created; phone service accepted message"
                except Exception:
                    self.delivery_status = "HA notification created; phone message queued for retry"
                    self.queue_phone(title, message)
            else:
                self.delivery_status = "HA notification created; phone service unavailable, message queued"
                self.queue_phone(title, message)
        self.history.append({"at": dt_util.utcnow().isoformat(), "title": title, "message": message})
        self.history = self.history[-10:]

    def queue_phone(self, title, message):
        now = dt_util.utcnow().timestamp()
        self.pending.append({"title": title, "message": message, "at": now, "retry_at": now + 60})
        self.pending = self.pending[-10:]

    async def async_retry_phone(self):
        target = self.entry.options.get("phone_notify_service", "none")
        if target == "none" or not target.startswith("mobile_app_"):
            return False
        now, changed = dt_util.utcnow().timestamp(), False
        for item in list(self.pending):
            if now - item["at"] > 86400:
                self.pending.remove(item)
                self.delivery_status = "Phone message expired after 24 hours; see HA message history"
                changed = True
                continue
            if now < item["retry_at"] or not self.hass.services.has_service("notify", target):
                continue
            item["retry_at"] = now + 60
            try:
                await self.hass.services.async_call("notify", target,
                    {"title": item["title"], "message": item["message"]}, blocking=True)
                self.pending.remove(item)
                self.delivery_status = "HA notification created; phone service accepted queued message"
            except Exception:
                self.delivery_status = "HA notification created; phone retry pending"
            changed = True
        return changed

    def values(self):
        enabled = self.entry.options.get("notifications_enabled", False)
        result = {"notification_status": self.delivery_status if enabled else "Disabled in integration options"}
        if self.history:
            result["last_notification"] = self.history[-1]["title"]
            result["last_notification_time"] = dt_util.parse_datetime(self.history[-1]["at"])
        return result

    async def async_test(self):
        async with self.lock:
            await self.async_send("test", "Test notification",
                "This is a notification test. No leak has been simulated and no water-valve command has been sent.")
            await self.store.async_save({"states": self.gate.states, "history": self.history,
                                         "delivery": self.delivery_status, "pending": self.pending})
            self.monitor.analytics.async_update_listeners()
