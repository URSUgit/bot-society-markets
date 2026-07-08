from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import MarketSessionStatus, MarketSessionWindow, MarketSessionsSnapshot

try:
    import pandas_market_calendars as market_calendars
except ImportError:  # pragma: no cover - exercised only when dependency is absent in an environment.
    market_calendars = None


@dataclass(frozen=True)
class MarketCalendarConfig:
    id: str
    region: str
    label: str
    exchange_code: str
    calendar: str
    city: str
    timezone: str
    note: str


MARKET_CALENDAR_CONFIGS = [
    MarketCalendarConfig(
        id="us-equities",
        region="USA",
        label="NYSE / Nasdaq",
        exchange_code="XNYS",
        calendar="NYSE",
        city="New York",
        timezone="America/New_York",
        note="Holiday-aware US equity regular session calendar. Nasdaq follows the same core US equity holidays.",
    ),
    MarketCalendarConfig(
        id="tokyo-equities",
        region="Asia",
        label="Tokyo Stock Exchange",
        exchange_code="XTKS",
        calendar="JPX",
        city="Tokyo",
        timezone="Asia/Tokyo",
        note="Holiday-aware JPX calendar with exchange breaks when published by the calendar package.",
    ),
    MarketCalendarConfig(
        id="hong-kong-equities",
        region="Asia",
        label="Hong Kong Exchange",
        exchange_code="XHKG",
        calendar="HKEX",
        city="Hong Kong",
        timezone="Asia/Hong_Kong",
        note="Holiday-aware HKEX calendar with lunch break handling when published by the calendar package.",
    ),
    MarketCalendarConfig(
        id="shanghai-equities",
        region="Asia",
        label="Shanghai Stock Exchange",
        exchange_code="XSHG",
        calendar="SSE",
        city="Shanghai",
        timezone="Asia/Shanghai",
        note="Holiday-aware Shanghai Stock Exchange calendar with exchange breaks when published by the calendar package.",
    ),
]


def build_market_sessions_snapshot(now: datetime | None = None) -> MarketSessionsSnapshot:
    generated_at = _utc_now(now)
    if market_calendars is None:
        return MarketSessionsSnapshot(
            generated_at=_iso(generated_at),
            source="pandas_market_calendars",
            status="setup_required",
            holiday_aware=False,
            message="Install pandas_market_calendars to enable real holiday-aware stock exchange sessions.",
            sessions=[],
        )

    sessions = [_build_session_status(config, generated_at) for config in MARKET_CALENDAR_CONFIGS]
    return MarketSessionsSnapshot(
        generated_at=_iso(generated_at),
        source="pandas_market_calendars",
        status="live" if sessions else "unavailable",
        holiday_aware=True,
        message="Exchange sessions are generated from pandas_market_calendars. Keep the package updated for exchange rule changes.",
        sessions=sessions,
    )


def _build_session_status(config: MarketCalendarConfig, now_utc: datetime) -> MarketSessionStatus:
    calendar = market_calendars.get_calendar(config.calendar)
    local_tz = ZoneInfo(config.timezone)
    local_now = now_utc.astimezone(local_tz)
    start_date = local_now.date() - timedelta(days=3)
    end_date = local_now.date() + timedelta(days=14)
    schedule = calendar.schedule(start_date=start_date.isoformat(), end_date=end_date.isoformat())
    rows = list(schedule.iterrows())
    active_row = None
    next_row = None

    for session_date, row in rows:
        market_open = _as_utc(row["market_open"])
        market_close = _as_utc(row["market_close"])
        if market_open <= now_utc < market_close:
            active_row = (session_date, row)
            break_start = _optional_utc(row, "break_start")
            break_end = _optional_utc(row, "break_end")
            if break_start and break_end and break_start <= now_utc < break_end:
                return _session_payload(
                    config,
                    now_utc,
                    session_date=session_date.date() if hasattr(session_date, "date") else session_date,
                    row=row,
                    status="Break",
                    phase="Lunch break",
                    is_open=False,
                    is_trading_day=True,
                    countdown_target=break_end,
                    countdown_label="Reopens in",
                )
            return _session_payload(
                config,
                now_utc,
                session_date=session_date.date() if hasattr(session_date, "date") else session_date,
                row=row,
                status="Open",
                phase="Regular session",
                is_open=True,
                is_trading_day=True,
                countdown_target=market_close,
                countdown_label="Closes in",
            )
        if market_open > now_utc and next_row is None:
            next_row = (session_date, row)

    current_session = _row_for_local_date(rows, local_now.date())
    if current_session is not None:
        session_date, row = current_session
        market_close = _as_utc(row["market_close"])
        if now_utc >= market_close:
            status = "Closed"
            phase = "After close"
        else:
            status = "Closed"
            phase = "Before open"
    else:
        status = "Closed"
        phase = "Holiday / weekend"

    target_row = next_row or _first_future_row(rows, now_utc)
    target_date, target_schedule = target_row if target_row else (None, None)
    next_open = _as_utc(target_schedule["market_open"]) if target_schedule is not None else None
    reference_row = current_session[1] if current_session is not None else target_schedule
    reference_date = current_session[0] if current_session is not None else target_date
    return _session_payload(
        config,
        now_utc,
        session_date=reference_date.date() if hasattr(reference_date, "date") else reference_date,
        row=reference_row,
        status=status,
        phase=phase,
        is_open=False,
        is_trading_day=current_session is not None,
        countdown_target=next_open,
        countdown_label="Opens in",
    )


def _session_payload(
    config: MarketCalendarConfig,
    now_utc: datetime,
    *,
    session_date: date | None,
    row,
    status: str,
    phase: str,
    is_open: bool,
    is_trading_day: bool,
    countdown_target: datetime | None,
    countdown_label: str,
) -> MarketSessionStatus:
    local_tz = ZoneInfo(config.timezone)
    market_open = _as_utc(row["market_open"]) if row is not None else None
    market_close = _as_utc(row["market_close"]) if row is not None else None
    windows = _session_windows(row, local_tz, is_open=is_open, now_utc=now_utc)
    return MarketSessionStatus(
        id=config.id,
        region=config.region,
        label=config.label,
        exchange_code=config.exchange_code,
        calendar=config.calendar,
        city=config.city,
        timezone=config.timezone,
        status=status,
        phase=phase,
        is_open=is_open,
        is_trading_day=is_trading_day,
        next_open=_iso(countdown_target) if countdown_label.startswith("Open") and countdown_target else None,
        next_close=_iso(market_close) if market_close and now_utc < market_close else None,
        countdown_target=_iso(countdown_target) if countdown_target else None,
        countdown_label=countdown_label,
        local_time=now_utc.astimezone(local_tz).isoformat(),
        market_open=_iso(market_open) if market_open else None,
        market_close=_iso(market_close) if market_close else None,
        windows=windows,
        note=_session_note(config, session_date, status, is_trading_day),
    )


def _session_windows(row, local_tz: ZoneInfo, *, is_open: bool, now_utc: datetime) -> list[MarketSessionWindow]:
    if row is None:
        return []
    market_open = _as_utc(row["market_open"])
    market_close = _as_utc(row["market_close"])
    break_start = _optional_utc(row, "break_start")
    break_end = _optional_utc(row, "break_end")
    if break_start and break_end:
        return [
            _window("Morning", market_open, break_start, local_tz, now_utc),
            _window("Afternoon", break_end, market_close, local_tz, now_utc),
        ]
    return [_window("Regular", market_open, market_close, local_tz, now_utc, force_open=is_open)]


def _window(
    label: str,
    start: datetime,
    end: datetime,
    local_tz: ZoneInfo,
    now_utc: datetime,
    *,
    force_open: bool = False,
) -> MarketSessionWindow:
    active = force_open or start <= now_utc < end
    return MarketSessionWindow(
        label=label,
        start=start.astimezone(local_tz).isoformat(),
        end=end.astimezone(local_tz).isoformat(),
        status="open" if active else ("complete" if now_utc >= end else "upcoming"),
    )


def _row_for_local_date(rows, target_date: date):
    for session_date, row in rows:
        row_date = session_date.date() if hasattr(session_date, "date") else session_date
        if row_date == target_date:
            return session_date, row
    return None


def _first_future_row(rows, now_utc: datetime):
    for session_date, row in rows:
        if _as_utc(row["market_open"]) > now_utc:
            return session_date, row
    return None


def _optional_utc(row, key: str) -> datetime | None:
    if key not in row or row[key] is None:
        return None
    value = row[key]
    if getattr(value, "tzinfo", None) is None and str(value) == "NaT":
        return None
    try:
        if value != value:
            return None
    except TypeError:
        return None
    return _as_utc(value)


def _as_utc(value) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_now(now: datetime | None = None) -> datetime:
    active = now or datetime.now(timezone.utc)
    if active.tzinfo is None:
        return active.replace(tzinfo=timezone.utc)
    return active.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _session_note(config: MarketCalendarConfig, session_date: date | None, status: str, is_trading_day: bool) -> str:
    if not is_trading_day:
        return f"{config.note} Current local date is not a scheduled trading day."
    if status == "Open":
        return config.note
    date_copy = session_date.isoformat() if session_date else "next scheduled session"
    return f"{config.note} Reference session: {date_copy}."
