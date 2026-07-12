#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

from market_config import load_market_config


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
POSITIONING_DIR = DATA_DIR / "positioning"
REGSHO_DIR = POSITIONING_DIR / "finra_regsho"
CBOE_DIR = POSITIONING_DIR / "cboe_options"


def safe_filename(ticker: str) -> str:
    return ticker.replace("-", "_").replace(".", "_")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def number(value: float | None, digits: int = 4) -> float | str:
    if value is None or not math.isfinite(value):
        return ""
    return round(value, digits)


def pct(value: float | None) -> float | str:
    if value is None or not math.isfinite(value):
        return ""
    return round(value * 100, 4)


def previous_weekdays(end_date: date, count: int) -> list[date]:
    days = []
    current = end_date - timedelta(days=1)
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current -= timedelta(days=1)
    return sorted(days)


def write_finra_regsho_config(days: int = 10) -> None:
    config = load_market_config()
    REGSHO_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["location", "retry = 1", "retry-delay = 1"]
    for day in previous_weekdays(config.end_date, days):
        ymd = day.strftime("%Y%m%d")
        lines.extend(
            [
                f'url = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{ymd}.txt"',
                f'output = "{REGSHO_DIR / f"CNMSshvol{ymd}.txt"}"',
            ]
        )
    (POSITIONING_DIR / "finra_regsho_curl.cfg").write_text("\n".join(lines) + "\n")


def write_cboe_options_config() -> None:
    config = load_market_config()
    CBOE_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        'user-agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"',
        "location",
        "retry = 1",
        "retry-delay = 1",
    ]
    for holding in sorted({h.ticker: h for h in config.holdings}.values(), key=lambda h: h.ticker):
        if "-" in holding.ticker:
            continue
        lines.extend(
            [
                f'url = "https://cdn.cboe.com/api/global/delayed_quotes/options/{holding.ticker}.json"',
                f'output = "{CBOE_DIR / (safe_filename(holding.ticker) + ".json")}"',
            ]
        )
    (POSITIONING_DIR / "cboe_options_curl.cfg").write_text("\n".join(lines) + "\n")


def parse_regsho_file(path: Path) -> list[dict]:
    text = path.read_text(errors="ignore")
    if not text.startswith("Date|Symbol|ShortVolume|"):
        return []
    rows = []
    reader = csv.DictReader(text.splitlines(), delimiter="|")
    for row in reader:
        rows.append(row)
    return rows


def analyze_short_volume() -> list[dict]:
    config = load_market_config()
    tickers = sorted({h.ticker for h in config.holdings if "-" not in h.ticker})
    rows_by_ticker: dict[str, list[dict]] = {ticker: [] for ticker in tickers}
    for path in sorted(REGSHO_DIR.glob("CNMSshvol*.txt")):
        for row in parse_regsho_file(path):
            ticker = row.get("Symbol", "")
            if ticker in rows_by_ticker:
                try:
                    short_volume = float(row["ShortVolume"])
                    total_volume = float(row["TotalVolume"])
                except Exception:
                    continue
                rows_by_ticker[ticker].append(
                    {
                        "date": row["Date"],
                        "short_volume": short_volume,
                        "short_exempt_volume": float(row.get("ShortExemptVolume") or 0),
                        "total_volume": total_volume,
                        "ratio": short_volume / total_volume if total_volume else None,
                        "market": row.get("Market", ""),
                    }
                )
    output = []
    for ticker in tickers:
        rows = sorted(rows_by_ticker[ticker], key=lambda row: row["date"])
        latest = rows[-1] if rows else None
        ratios = [row["ratio"] for row in rows[-5:] if row["ratio"] is not None]
        output.append(
            {
                "ticker": ticker,
                "coverage_status": "full" if latest else "missing",
                "source": "FINRA daily short sale volume",
                "as_of_date": latest["date"] if latest else "",
                "short_volume": number(latest["short_volume"], 2) if latest else "",
                "short_exempt_volume": number(latest["short_exempt_volume"], 2) if latest else "",
                "total_volume": number(latest["total_volume"], 2) if latest else "",
                "short_volume_ratio_pct": pct(latest["ratio"]) if latest else "",
                "avg_5file_short_volume_ratio_pct": pct(mean(ratios)) if ratios else "",
                "files_used": len(rows),
                "note": "Daily short sale volume is a flow proxy, not bi-monthly short interest.",
            }
        )
    for holding in sorted({h.ticker: h for h in config.holdings if "-" in h.ticker}.values(), key=lambda h: h.ticker):
        output.append(
            {
                "ticker": holding.ticker,
                "coverage_status": "not_applicable",
                "source": "FINRA daily short sale volume",
                "as_of_date": "",
                "short_volume": "",
                "short_exempt_volume": "",
                "total_volume": "",
                "short_volume_ratio_pct": "",
                "avg_5file_short_volume_ratio_pct": "",
                "files_used": 0,
                "note": "Crypto pairs do not have FINRA short sale volume.",
            }
        )
    return sorted(output, key=lambda row: row["ticker"])


OPTION_RE = re.compile(r"(\d{6})([CP])(\d{8})$")


def parse_option_side(option_symbol: str) -> str | None:
    match = OPTION_RE.search(option_symbol)
    if not match:
        return None
    return "call" if match.group(2) == "C" else "put"


def analyze_options() -> list[dict]:
    config = load_market_config()
    rows = []
    for holding in sorted({h.ticker: h for h in config.holdings}.values(), key=lambda h: h.ticker):
        if "-" in holding.ticker:
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": "not_applicable",
                    "source": "Cboe delayed options",
                    "as_of_timestamp": "",
                    "call_open_interest": "",
                    "put_open_interest": "",
                    "put_call_open_interest_ratio": "",
                    "call_volume": "",
                    "put_volume": "",
                    "put_call_volume_ratio": "",
                    "median_iv_pct": "",
                    "contracts_count": 0,
                    "note": "Crypto pairs do not have listed equity options in this source.",
                }
            )
            continue
        path = CBOE_DIR / f"{safe_filename(holding.ticker)}.json"
        if not path.exists():
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": "missing",
                    "source": "Cboe delayed options",
                    "as_of_timestamp": "",
                    "call_open_interest": "",
                    "put_open_interest": "",
                    "put_call_open_interest_ratio": "",
                    "call_volume": "",
                    "put_volume": "",
                    "put_call_volume_ratio": "",
                    "median_iv_pct": "",
                    "contracts_count": 0,
                    "note": "Cboe options file has not been downloaded.",
                }
            )
            continue
        try:
            payload = json.loads(path.read_text())
            options = payload.get("data", {}).get("options", [])
        except Exception:
            options = []
            payload = {}
        call_oi = put_oi = call_volume = put_volume = 0.0
        ivs = []
        for option in options:
            side = parse_option_side(str(option.get("option", "")))
            if side is None:
                continue
            open_interest = float(option.get("open_interest") or 0)
            volume = float(option.get("volume") or 0)
            iv = float(option.get("iv") or 0)
            if iv > 0:
                ivs.append(iv)
            if side == "call":
                call_oi += open_interest
                call_volume += volume
            else:
                put_oi += open_interest
                put_volume += volume
        coverage = "full" if options else "missing"
        rows.append(
            {
                "ticker": holding.ticker,
                "coverage_status": coverage,
                "source": "Cboe delayed options",
                "as_of_timestamp": payload.get("timestamp", ""),
                "call_open_interest": number(call_oi, 2) if options else "",
                "put_open_interest": number(put_oi, 2) if options else "",
                "put_call_open_interest_ratio": number(put_oi / call_oi if call_oi else None),
                "call_volume": number(call_volume, 2) if options else "",
                "put_volume": number(put_volume, 2) if options else "",
                "put_call_volume_ratio": number(put_volume / call_volume if call_volume else None),
                "median_iv_pct": pct(median(ivs)) if ivs else "",
                "contracts_count": len(options),
                "note": "Snapshot only; not historical options positioning." if options else "No usable Cboe options data.",
            }
        )
    return rows


def aggregate(short_rows: list[dict], option_rows: list[dict]) -> list[dict]:
    config = load_market_config()
    short_by_ticker = {row["ticker"]: row for row in short_rows}
    option_by_ticker = {row["ticker"]: row for row in option_rows}
    rows = []
    for basket in config.baskets:
        short_items = [short_by_ticker.get(h.ticker) for h in basket.holdings if h.ticker in short_by_ticker]
        option_items = [option_by_ticker.get(h.ticker) for h in basket.holdings if h.ticker in option_by_ticker]
        short_usable = [row for row in short_items if row["coverage_status"] == "full"]
        option_usable = [row for row in option_items if row["coverage_status"] == "full"]

        def values(items: list[dict], field: str) -> list[float]:
            return [float(row[field]) for row in items if row.get(field) not in {"", None}]

        row = {
            "basket": basket.id,
            "constituents": len(basket.holdings),
            "short_volume_coverage_count": len(short_usable),
            "short_volume_coverage_pct": round(len(short_usable) / len(basket.holdings) * 100, 4),
            "options_coverage_count": len(option_usable),
            "options_coverage_pct": round(len(option_usable) / len(basket.holdings) * 100, 4),
            "median_short_volume_ratio_pct": number(median(values(short_usable, "short_volume_ratio_pct")) if values(short_usable, "short_volume_ratio_pct") else None),
            "median_5file_short_volume_ratio_pct": number(median(values(short_usable, "avg_5file_short_volume_ratio_pct")) if values(short_usable, "avg_5file_short_volume_ratio_pct") else None),
            "median_put_call_open_interest_ratio": number(median(values(option_usable, "put_call_open_interest_ratio")) if values(option_usable, "put_call_open_interest_ratio") else None),
            "median_put_call_volume_ratio": number(median(values(option_usable, "put_call_volume_ratio")) if values(option_usable, "put_call_volume_ratio") else None),
            "median_options_iv_pct": number(median(values(option_usable, "median_iv_pct")) if values(option_usable, "median_iv_pct") else None),
        }
        rows.append(row)
    return rows


def analyze() -> None:
    short_rows = analyze_short_volume()
    option_rows = analyze_options()
    write_csv(
        DATA_DIR / "short_volume_metrics.csv",
        [
            "ticker",
            "coverage_status",
            "source",
            "as_of_date",
            "short_volume",
            "short_exempt_volume",
            "total_volume",
            "short_volume_ratio_pct",
            "avg_5file_short_volume_ratio_pct",
            "files_used",
            "note",
        ],
        short_rows,
    )
    write_csv(
        DATA_DIR / "options_positioning_metrics.csv",
        [
            "ticker",
            "coverage_status",
            "source",
            "as_of_timestamp",
            "call_open_interest",
            "put_open_interest",
            "put_call_open_interest_ratio",
            "call_volume",
            "put_volume",
            "put_call_volume_ratio",
            "median_iv_pct",
            "contracts_count",
            "note",
        ],
        option_rows,
    )
    write_csv(
        DATA_DIR / "basket_positioning.csv",
        [
            "basket",
            "constituents",
            "short_volume_coverage_count",
            "short_volume_coverage_pct",
            "options_coverage_count",
            "options_coverage_pct",
            "median_short_volume_ratio_pct",
            "median_5file_short_volume_ratio_pct",
            "median_put_call_open_interest_ratio",
            "median_put_call_volume_ratio",
            "median_options_iv_pct",
        ],
        aggregate(short_rows, option_rows),
    )
    coverage_rows = []
    for row in aggregate(short_rows, option_rows):
        coverage_rows.append(
            {
                "basket": row["basket"],
                "short_volume_coverage_pct": row["short_volume_coverage_pct"],
                "options_coverage_pct": row["options_coverage_pct"],
                "short_interest_status": "not_collected",
                "short_interest_note": "Bi-monthly short interest requires a separate source/API; FINRA daily short sale volume is collected as a flow proxy.",
            }
        )
    write_csv(
        DATA_DIR / "positioning_coverage.csv",
        [
            "basket",
            "short_volume_coverage_pct",
            "options_coverage_pct",
            "short_interest_status",
            "short_interest_note",
        ],
        coverage_rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["write-finra-config", "write-cboe-config", "analyze"],
    )
    parser.add_argument("--days", type=int, default=10)
    args = parser.parse_args()
    if args.command == "write-finra-config":
        write_finra_regsho_config(args.days)
    elif args.command == "write-cboe-config":
        write_cboe_options_config()
    elif args.command == "analyze":
        analyze()


if __name__ == "__main__":
    main()
