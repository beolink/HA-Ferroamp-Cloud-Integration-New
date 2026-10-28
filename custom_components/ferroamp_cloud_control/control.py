"""Battery control: the EMS inverter contract's setpoint, written as
configuration schedules.

The system follows schedules (PROTOCOL.md). A schedule takes effect at its
start, the one that started last stands, and the end of a schedule does
nothing. So a command is a one-off manual schedule that starts at the next
whole minute and runs ``WINDOW_S``, followed by a return schedule that starts
at the end of that window with the owner's own configuration. A command
stands only while it is renewed. When the renewals stop, because Home
Assistant is down or the link is gone, the return starts and the system goes
back to what the owner set.

Every write creates the return first, then the manual schedule, and then
removes what the previous write left behind. Only schedules whose summary
starts with ``CONTROL_PREFIX`` are ever removed.

Signs are EMS's: positive charges, negative discharges, and 0 hands the
system back to its own configuration.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

from . import protocol
from .api import AuthError, CloudError
from .const import CONTROL_PREFIX, MODE_IDLE, MODE_SELF_CONSUMPTION, REFRESH_S, RETURN_SUMMARY, START_LEAD_S, WINDOW_S

_LOGGER = logging.getLogger(__name__)

WINDOW = dt.timedelta(seconds=WINDOW_S)
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)

# What the entities say while the switch is off.
CONTROL_OFF = "control is off"
HANDED_BACK = "control is off; the owner's configuration is back"


class ControlRefused(Exception):
    """The cloud refused a schedule, or the system cannot take one now. The
    message is what the entities show."""


def next_start(now: dt.datetime) -> dt.datetime:
    """The first whole minute at least START_LEAD_S after ``now``."""
    lead = now + dt.timedelta(seconds=START_LEAD_S)
    floor = lead.replace(second=0, microsecond=0)
    return floor if floor == lead else floor + dt.timedelta(minutes=1)


def is_hand_back(setpoint_w: float) -> bool:
    """EMS's 0: the system goes back to its own configuration."""
    return round(setpoint_w) == 0


@dataclass(frozen=True)
class Target:
    """A fixed battery reference: charge or discharge, never both."""

    charge_w: int
    discharge_w: int

    @property
    def action(self) -> str:
        return "charge" if self.charge_w else "discharge"

    @property
    def summary(self) -> str:
        return f"{CONTROL_PREFIX} {self.action} {self.charge_w or self.discharge_w} W"


def target_for(setpoint_w: float, rated_w: float) -> Target:
    """The reference for a setpoint, never above the battery's rated power."""
    watts = int(round(min(abs(setpoint_w), rated_w)))
    if setpoint_w > 0:
        return Target(charge_w=watts, discharge_w=0)
    return Target(charge_w=0, discharge_w=watts)


@dataclass(frozen=True)
class Plan:
    """One write: the schedules to create, in order, and the ones to remove
    once they are in. ``target`` is None when the system is handed back."""

    creates: tuple[tuple[str, dict[str, Any]], ...]   # ("return" or "manual", schedule input)
    removes: tuple[str, ...]
    target: Target | None


def _in_force(owned: tuple[protocol.Schedule, ...], now: dt.datetime) -> protocol.Schedule | None:
    """The schedule the system runs now: the latest one that has started."""
    started = [s for s in owned if s.start is not None and s.start <= now]
    return max(started, key=lambda s: s.start) if started else None


def _is_future(schedule: protocol.Schedule, now: dt.datetime) -> bool:
    return schedule.start is not None and schedule.start > now


def plan_write(setpoint_w: float, *, now: dt.datetime, start: dt.datetime, rated_w: float, timezone: str,
               normal: dict[str, Any], owned: tuple[protocol.Schedule, ...]) -> Plan:
    """What a write does, given the owner's configuration ``normal`` (as
    ``protocol.config_input`` shapes it) and the schedules the driver owns.

    The schedule in force is never removed: the cloud runs the one that started
    last, and taking it out could bring back an older one for the seconds before
    the new one starts. What is removed is every other schedule of the driver's,
    which are earlier commands and returns that have not come due yet."""
    keep = _in_force(owned, now)
    removes = tuple(s.id for s in owned if s is not keep)
    if is_hand_back(setpoint_w):
        if not owned:
            return Plan(creates=(), removes=(), target=None)
        already_back = (keep is not None and keep.summary == RETURN_SUMMARY
                        and not any(_is_future(s, now) for s in owned))
        if already_back:
            return Plan(creates=(), removes=removes, target=None)
        back = protocol.schedule_input(RETURN_SUMMARY, start, start + WINDOW, timezone, normal)
        return Plan(creates=(("return", back),), removes=removes, target=None)
    target = target_for(setpoint_w, rated_w)
    end = start + WINDOW
    manual = protocol.schedule_input(
        target.summary, start, end, timezone,
        protocol.manual_config_input(normal, target.charge_w, target.discharge_w))
    back = protocol.schedule_input(RETURN_SUMMARY, end, end + WINDOW, timezone, normal)
    return Plan(creates=(("return", back), ("manual", manual)), removes=removes, target=target)


def _refusal(answer: dict[str, Any]) -> str:
    return answer.get("message") or answer.get("code") or "the cloud refused the schedule"


class Controller:
    """The switch and the setpoint, and the writes that make the cloud say
    them. One write at a time."""

    def __init__(self, client: Any, facility_id: int) -> None:
        self._client = client
        self._facility_id = facility_id
        self._lock = asyncio.Lock()
        # The owner's configuration, as last seen while no command stood.
        self._observed: dict[str, Any] | None = None
        self._last_write: dt.datetime | None = None
        self.enabled = False
        self.setpoint_w = 0.0
        self.mode = MODE_SELF_CONSUMPTION
        # Kept and reported, never sent: the cloud has no import cap to set. Same as ha-ferroamp-control.
        self.grid_limit_w: float | None = None
        self.result = "idle"    # idle, pending, ack (the cloud took it) or nak (it did not)
        self.reason: str | None = None
        self.command: dict[str, Any] = {}

    def effective_setpoint(self) -> float:
        """What the battery is asked for. Idle hands it back whatever the setpoint says."""
        return 0.0 if self.mode == MODE_IDLE else self.setpoint_w

    def observe(self, live: protocol.Live) -> None:
        """Keep the owner's configuration. A manual configuration is the
        driver's own command, so it is never kept."""
        raw = live.config_raw
        if raw and raw.get("systemMode") not in (None, protocol.MANUAL_MODE):
            self._observed = raw

    def renewal_due(self, now: dt.datetime) -> bool:
        """A standing command is written again every REFRESH_S, also when EMS
        does not write, so a missed tick does not end it."""
        return (self.enabled and not is_hand_back(self.effective_setpoint()) and self._last_write is not None
                and now - self._last_write >= dt.timedelta(seconds=REFRESH_S))

    async def write(self, setpoint_w: float, *, live: protocol.Live, info: protocol.Info | None,
                    now: dt.datetime) -> None:
        """Make the schedules say what ``setpoint_w`` asks, or say why not."""
        self.setpoint_w = setpoint_w
        self.observe(live)
        if not self.enabled:
            # EMS writes every tick, also with the switch off. The verdict on
            # handing back stands until the switch comes on again: a failed
            # hand-back stays a nak (tidy() clears it once the return is in
            # force), and a good one keeps its words.
            if self.result != "nak" and not (self.reason or "").startswith(CONTROL_OFF):
                self._set("idle", CONTROL_OFF)
            return
        async with self._lock:
            self._last_write = now
            self._set("pending", None)
            try:
                await self._apply(self.effective_setpoint(), live=live, info=info, now=now)
            except ControlRefused as err:
                self._set("nak", str(err))
            except (AuthError, CloudError) as err:
                _LOGGER.warning("Battery control write failed: %s", err)
                self._set("nak", f"the cloud did not answer: {err}")

    async def release(self, *, live: protocol.Live, info: protocol.Info | None, now: dt.datetime) -> None:
        """The switch went off: hand the system back at once, if a command of
        the driver's stands. Nothing is written when none does."""
        self.observe(live)
        async with self._lock:
            try:
                owned = await self._owned(now)
                if not owned:
                    self._set("idle", CONTROL_OFF)
                    return
                rated_w, timezone = self._check(live, info)
                start = next_start(now)
                plan = plan_write(0, now=now, start=start, rated_w=rated_w, timezone=timezone,
                                  normal=self._normal(owned), owned=owned)
                ids, failed = await self._execute(plan)
                command = self._command(plan, 0, start, ids)
                if failed:
                    self._set("nak", _removal_reason(failed), command)
                else:
                    self._set("idle", HANDED_BACK, command)
            except ControlRefused as err:
                self._set("nak", str(err))
            except (AuthError, CloudError) as err:
                _LOGGER.warning("Handing the battery back failed: %s", err)
                self._set("nak", f"the cloud did not answer: {err}")

    async def tidy(self, now: dt.datetime) -> None:
        """While the switch is off, remove the driver's schedules that are no
        longer in force. The one in force stays, and so does anything not yet
        due: that is the owner's configuration coming back."""
        if self.enabled:
            return
        async with self._lock:
            try:
                owned = await self._owned(now)
            except (AuthError, CloudError) as err:
                _LOGGER.debug("Control tidy skipped: %s", err)
                return
            keep = _in_force(owned, now)
            stale = tuple(s.id for s in owned if s is not keep and not _is_future(s, now))
            failed = 0
            if stale:
                _ids, failed = await self._execute(Plan(creates=(), removes=stale, target=None))
            if failed:
                self._set("nak", _removal_reason(failed))
            elif self.result == "nak" and (keep is None or keep.summary == RETURN_SUMMARY):
                # A hand-back that failed earlier is over: the return is in
                # force, or nothing of the driver's is.
                self._set("idle", HANDED_BACK)

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "setpoint_w": self.setpoint_w,
            "grid_limit_w": self.grid_limit_w,
            "result": self.result,
            "reason": self.reason,
            "command": self.command,
            "last_write": protocol.iso(self._last_write) if self._last_write else None,
        }

    async def _apply(self, setpoint_w: float, *, live: protocol.Live, info: protocol.Info | None,
                     now: dt.datetime) -> None:
        owned = await self._owned(now)
        if is_hand_back(setpoint_w) and not owned:
            self._set("ack", "the owner's configuration stands", {"action": "return", "setpoint_w": 0})
            return
        rated_w, timezone = self._check(live, info)
        start = next_start(now)
        plan = plan_write(setpoint_w, now=now, start=start, rated_w=rated_w, timezone=timezone,
                          normal=self._normal(owned), owned=owned)
        ids, failed = await self._execute(plan)
        command = self._command(plan, setpoint_w, start, ids)
        if failed:
            self._set("nak", _removal_reason(failed), command)
        else:
            self._set("ack", None, command)

    async def _owned(self, now: dt.datetime) -> tuple[protocol.Schedule, ...]:
        """The schedules the driver made, read fresh: after a restart they are
        the only record of a command that may still stand."""
        data = await self._client.query(
            protocol.SCHEDULES, protocol.schedule_variables(self._facility_id, now))
        return tuple(s for s in protocol.parse_schedules(data) if (s.summary or "").startswith(CONTROL_PREFIX))

    def _normal(self, owned: tuple[protocol.Schedule, ...]) -> dict[str, Any]:
        """The owner's configuration: the one seen while no command stood, or
        else the one the driver's last return schedule carries."""
        raw = self._observed
        if raw is None:
            returns = [s for s in owned if s.summary == RETURN_SUMMARY and s.config_raw]
            if returns:
                raw = max(returns, key=lambda s: s.start or _EPOCH).config_raw
        normal = protocol.config_input(raw)
        if normal is None:
            raise ControlRefused("the owner's configuration is not known yet")
        return normal

    @staticmethod
    def _check(live: protocol.Live, info: protocol.Info | None) -> tuple[float, str]:
        """What the cloud needs before it takes a schedule from the driver:
        FerroAI off (the cloud refuses owner schedules while it runs), a
        system on configuration schedules, and the battery's rating and time
        zone. Returns the rating and the time zone."""
        if live.ferroai_enabled is None:
            raise ControlRefused("the system's state is not known yet")
        if live.ferroai_enabled:
            raise ControlRefused("FerroAI is on, and the cloud refuses schedules then; turn FerroAI off")
        if info is None:
            raise ControlRefused("the system's details are not known yet")
        if info.uses_new_scheduler is not True:
            raise ControlRefused("the system takes no configuration schedules (EnergyHub OS 7 or later)")
        if not info.battery_max_w or not info.timezone:
            raise ControlRefused("the battery's rating or the system's time zone is not known yet")
        return info.battery_max_w, info.timezone

    async def _execute(self, plan: Plan) -> tuple[dict[str, str], int]:
        """Create the plan's schedules in order, then remove the old ones.
        Returns the new ids by role and how many removals failed."""
        ids: dict[str, str] = {}
        for role, data in plan.creates:
            ids[role] = await self._create(data)
        failed = 0
        for schedule_id in plan.removes:
            try:
                await self._remove(schedule_id)
            except (ControlRefused, CloudError) as err:
                _LOGGER.warning("Could not remove control schedule %s: %s", schedule_id, err)
                failed += 1
        return ids, failed

    async def _create(self, data: dict[str, Any]) -> str:
        answer = (await self._client.query(
            protocol.CREATE_SCHEDULE, {"facilityId": self._facility_id, "data": data})
        ).get("createOneNormalConfigurationSchedule") or {}
        schedule_id = (answer.get("schedule") or {}).get("id")
        if not answer.get("success") or schedule_id is None:
            raise ControlRefused(_refusal(answer))
        return str(schedule_id)

    async def _remove(self, schedule_id: str) -> None:
        answer = (await self._client.query(
            protocol.REMOVE_SCHEDULE, {"facilityId": self._facility_id, "id": schedule_id})
        ).get("removeOneNormalConfigurationSchedule") or {}
        if not answer.get("success"):
            raise ControlRefused(_refusal(answer))

    @staticmethod
    def _command(plan: Plan, setpoint_w: float, start: dt.datetime, ids: dict[str, str]) -> dict[str, Any]:
        if plan.target is None:
            return {"action": "return", "setpoint_w": 0,
                    "return_at": protocol.iso(start) if "return" in ids else None,
                    "return_id": ids.get("return")}
        return {
            "action": plan.target.action,
            "setpoint_w": setpoint_w,
            "charge_w": plan.target.charge_w,
            "discharge_w": plan.target.discharge_w,
            "window_start": protocol.iso(start),
            "window_end": protocol.iso(start + WINDOW),
            "manual_id": ids.get("manual"),
            "return_id": ids.get("return"),
        }

    def _set(self, result: str, reason: str | None, command: dict[str, Any] | None = None) -> None:
        self.result = result
        self.reason = reason
        if command is not None:
            self.command = command


def _removal_reason(failed: int) -> str:
    return f"{failed} earlier schedule(s) could not be removed; the next write tries again"
