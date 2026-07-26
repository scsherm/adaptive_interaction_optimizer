#!/usr/bin/env python3
"""Market config surface plus the US equity trading calendar.

Basket definitions now live in `universe.py` / `config/universe.yaml`; this
module re-exports that model under its historical names and owns the session
calendar used to keep the analysis window current.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from universe import (
    Basket,
    Holding,
    Universe,
    UniverseError,
    UNIVERSE_PATH,
    load_universe,
    load_universe_data,
    save_universe_data,
)


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = UNIVERSE_PATH
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)

# The canonical model is `Universe`; MarketConfig is kept as an alias because a
# dozen modules annotate against it.
MarketConfig = Universe

__all__ = [
    "ROOT",
    "CONFIG_PATH",
    "MARKET_TZ",
    "MARKET_CLOSE",
    "Basket",
    "Holding",
    "MarketConfig",
    "Universe",
    "UniverseError",
    "load_market_config",
    "load_config_data",
    "save_config_data",
    "parse_date",
    "human_date",
    "market_data_status",
    "is_us_equity_trading_day",
    "us_equity_market_holidays",
    "latest_completed_us_equity_session",
    "sync_config_end_date",
]


def load_market_config(path: Path = CONFIG_PATH) -> MarketConfig:
    return load_universe(path)


def load_config_data(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return load_universe_data(path)


def save_config_data(data: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    save_universe_data(data, path)


def parse_date(value: str) -> date:
    return date.fromisoformat(str(value))


# ---------------------------------------------------------------------------
# US equity trading calendar
# ---------------------------------------------------------------------------


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    offset = (weekday - current.weekday()) % 7
    return current + timedelta(days=offset + (n - 1) * 7)


def last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def easter_date(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def us_equity_market_holidays(year: int) -> set[date]:
    holidays = {
        observed_fixed_holiday(year, 1, 1),
        observed_fixed_holiday(year + 1, 1, 1),
        nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        easter_date(year) - timedelta(days=2),  # Good Friday
        last_weekday(year, 5, 0),  # Memorial Day
        observed_fixed_holiday(year, 6, 19),  # Juneteenth
        observed_fixed_holiday(year, 7, 4),
        nth_weekday(year, 9, 0, 1),  # Labor Day
        nth_weekday(year, 11, 3, 4),  # Thanksgiving
        observed_fixed_holiday(year, 12, 25),
    }
    return {day for day in holidays if day.year == year}


def is_us_equity_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day not in us_equity_market_holidays(day.year)


def latest_completed_us_equity_session(now: datetime | None = None) -> date:
    current = now or datetime.now(MARKET_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=MARKET_TZ)
    else:
        current = current.astimezone(MARKET_TZ)

    candidate = current.date()
    if not is_us_equity_trading_day(candidate) or current.time() < MARKET_CLOSE:
        candidate -= timedelta(days=1)
    while not is_us_equity_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def human_date(day: date) -> str:
    return f"{day:%B} {day.day}, {day:%Y}"


def market_data_status(end_date: date, now: datetime | None = None) -> str:
    current = now or datetime.now(MARKET_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=MARKET_TZ)
    else:
        current = current.astimezone(MARKET_TZ)
    return (
        f"{human_date(end_date)} is the latest completed U.S. equity session "
        f"as of {human_date(current.date())}. The pipeline auto-updates this date before rebuilds."
    )


def sync_config_end_date(
    target_date: date | None = None,
    *,
    now: datetime | None = None,
    path: Path = CONFIG_PATH,
) -> dict[str, Any]:
    data = load_config_data(path)
    methodology = data["methodology"]
    current_end = parse_date(str(methodology["end_date"]))
    latest = target_date or latest_completed_us_equity_session(now)
    start = parse_date(str(methodology["start_date"]))
    if latest < start:
        raise ValueError(
            f"Latest completed session {latest.isoformat()} is before configured start {start.isoformat()}"
        )

    status = market_data_status(latest, now)
    date_changed = current_end != latest
    status_changed = methodology.get("data_status", "") != status
    changed = date_changed or status_changed
    if changed:
        methodology["end_date"] = latest.isoformat()
        methodology["data_status"] = status
        save_config_data(data, path)
    return {
        "changed": changed,
        "dateChanged": date_changed,
        "statusChanged": status_changed,
        "previousEndDate": current_end.isoformat(),
        "endDate": latest.isoformat(),
        "dataStatus": status,
    }
