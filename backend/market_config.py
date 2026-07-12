#!/usr/bin/env python3
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "baskets.yaml"
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)


@dataclass(frozen=True)
class Holding:
    basket: str
    ticker: str
    name: str
    note: str


@dataclass(frozen=True)
class Basket:
    id: str
    label: str
    short: str
    color: str
    accent: str
    holdings: list[Holding]


@dataclass(frozen=True)
class MarketConfig:
    start_date: date
    end_date: date
    expected_constituents_per_basket: int
    source: str
    weighting: str
    price_field: str
    data_status: str
    baskets: list[Basket]
    benchmarks: list[Holding]
    symbol_decisions: list[str]

    @property
    def holdings(self) -> list[Holding]:
        return [holding for basket in self.baskets for holding in basket.holdings]

    @property
    def basket_labels(self) -> dict[str, str]:
        return {basket.id: basket.label for basket in self.baskets}

    @property
    def basket_meta(self) -> dict[str, dict[str, str]]:
        return {
            basket.id: {
                "label": basket.label,
                "short": basket.short,
                "color": basket.color,
                "accent": basket.accent,
            }
            for basket in self.baskets
        }


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value[0] in {"'", '"'}:
        return json.loads(value)
    if value in {"true", "false"}:
        return value == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def split_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"Expected key/value pair: {text!r}")
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def load_minimal_yaml(path: Path) -> dict[str, Any]:
    raw_lines = path.read_text().splitlines()
    lines = [
        line.rstrip()
        for line in raw_lines
        if line.strip() and not line.lstrip().startswith("#")
    ]

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        if indentation(lines[index]) < indent:
            return {}, index
        is_list = lines[index].lstrip().startswith("- ")
        if is_list:
            values: list[Any] = []
            while index < len(lines):
                line = lines[index]
                current_indent = indentation(line)
                if current_indent != indent or not line.lstrip().startswith("- "):
                    break
                content = line.strip()[2:].strip()
                index += 1
                if not content:
                    child, index = parse_block(index, indent + 2)
                    values.append(child)
                    continue
                if ":" in content:
                    key, value = split_key_value(content)
                    item: dict[str, Any] = {
                        key: parse_scalar(value) if value else {},
                    }
                    if index < len(lines) and indentation(lines[index]) > indent:
                        child, index = parse_block(index, indent + 2)
                        if isinstance(child, dict):
                            item.update(child)
                        elif value:
                            item[key] = child
                    values.append(item)
                    continue
                values.append(parse_scalar(content))
            return values, index

        values: dict[str, Any] = {}
        while index < len(lines):
            line = lines[index]
            current_indent = indentation(line)
            if current_indent < indent:
                break
            if current_indent != indent or line.lstrip().startswith("- "):
                break
            key, value = split_key_value(line.strip())
            index += 1
            if value:
                values[key] = parse_scalar(value)
            else:
                child, index = parse_block(index, indent + 2)
                values[key] = child
        return values, index

    parsed, next_index = parse_block(0, 0)
    if next_index != len(lines):
        raise ValueError(f"Could not parse {path}: stopped at line {next_index + 1}")
    if not isinstance(parsed, dict):
        raise ValueError(f"Top-level config must be a mapping: {path}")
    return parsed


def quote_yaml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def dump_baskets_yaml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    methodology = data["methodology"]
    lines.append("methodology:")
    for key in [
        "start_date",
        "end_date",
        "expected_constituents_per_basket",
        "source",
        "weighting",
        "price_field",
        "data_status",
    ]:
        lines.append(f"  {key}: {quote_yaml(methodology[key])}")
    lines.append("")
    lines.append("benchmarks:")
    for row in data["benchmarks"]:
        lines.append(f"  - ticker: {row['ticker']}")
        lines.append(f"    name: {quote_yaml(row['name'])}")
        lines.append(f"    note: {quote_yaml(row['note'])}")
    lines.append("")
    lines.append("symbol_decisions:")
    for item in data["symbol_decisions"]:
        lines.append(f"  - {quote_yaml(item)}")
    lines.append("")
    lines.append("baskets:")
    for basket in data["baskets"]:
        lines.append(f"  - id: {basket['id']}")
        lines.append(f"    label: {quote_yaml(basket['label'])}")
        lines.append(f"    short: {quote_yaml(basket['short'])}")
        lines.append(f"    color: {quote_yaml(basket['color'])}")
        lines.append(f"    accent: {quote_yaml(basket['accent'])}")
        lines.append("    holdings:")
        for holding in basket["holdings"]:
            lines.append(f"      - ticker: {holding['ticker']}")
            lines.append(f"        name: {quote_yaml(holding['name'])}")
            lines.append(f"        note: {quote_yaml(holding['note'])}")
    return "\n".join(lines) + "\n"


def load_config_data(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return deepcopy(load_minimal_yaml(path))


def save_config_data(data: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.write_text(dump_baskets_yaml(data))


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


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
        raise ValueError(f"Latest completed session {latest.isoformat()} is before configured start {start.isoformat()}")

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


def load_market_config(path: Path = CONFIG_PATH) -> MarketConfig:
    data = load_minimal_yaml(path)
    methodology = data["methodology"]
    baskets = []
    for basket_row in data["baskets"]:
        basket_id = basket_row["id"]
        holdings = [
            Holding(
                basket=basket_id,
                ticker=row["ticker"],
                name=row["name"],
                note=row["note"],
            )
            for row in basket_row["holdings"]
        ]
        baskets.append(
            Basket(
                id=basket_id,
                label=basket_row["label"],
                short=basket_row["short"],
                color=basket_row["color"],
                accent=basket_row["accent"],
                holdings=holdings,
            )
        )
    benchmarks = [
        Holding(
            basket="benchmark",
            ticker=row["ticker"],
            name=row["name"],
            note=row["note"],
        )
        for row in data["benchmarks"]
    ]
    return MarketConfig(
        start_date=parse_date(methodology["start_date"]),
        end_date=parse_date(methodology["end_date"]),
        expected_constituents_per_basket=int(methodology["expected_constituents_per_basket"]),
        source=methodology["source"],
        weighting=methodology["weighting"],
        price_field=methodology["price_field"],
        data_status=methodology["data_status"],
        baskets=baskets,
        benchmarks=benchmarks,
        symbol_decisions=list(data["symbol_decisions"]),
    )
