#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from build_market_dashboard import BASKET_META, DATA_DIR, ROOT, build_data


OUTPUT = ROOT / "market-basket-analyst-workstation.html"


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def read_json(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def enhance_data(data: dict) -> dict:
    breadth: dict[str, list[dict]] = {basket: [] for basket in BASKET_META}
    for row in read_csv("basket_breadth_daily.csv"):
        basket = row.get("basket", "")
        if basket not in breadth:
            continue
        breadth[basket].append(
            {
                "date": row.get("date", ""),
                "positiveSinceStartPct": float(row.get("positive_since_start_pct") or 0),
                "above10dmaPct": float(row.get("above_10dma_pct") or 0),
                "atWindowHighPct": float(row.get("at_window_high_pct") or 0),
                "reporting": int(float(row.get("constituents_reporting") or 0)),
                "total": int(float(row.get("constituents_total") or 0)),
            }
        )

    source_metadata = {}
    for row in read_csv("source_metadata.csv"):
        ticker = row.get("ticker", "")
        if not ticker:
            continue
        source_metadata[ticker] = {
            "sourceSymbol": row.get("source_symbol", ""),
            "instrumentType": row.get("instrument_type", ""),
            "exchange": row.get("exchange", ""),
            "regularMarketTime": row.get("regular_market_time", ""),
            "lastDate": row.get("last_date", ""),
            "rowCount": int(float(row.get("row_count") or 0)),
        }

    data["breadth"] = breadth
    data["sourceMetadata"] = source_metadata
    data["qa"] = read_json("qa_report.json")
    data["analystGeneratedAt"] = datetime.now(UTC).isoformat(timespec="seconds")
    return data


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Basket Analyst Workstation</title>
  <style>
    :root {
      --bg: #eef1ec;
      --panel: #ffffff;
      --panel-soft: #f7f8f4;
      --ink: #151814;
      --muted: #4f594f;
      --faint: #737c71;
      --line: #cbd5c6;
      --line-strong: #9ea99a;
      --green: #066b4d;
      --green-soft: #dceee6;
      --teal: #087986;
      --teal-soft: #dbecee;
      --red: #b32630;
      --red-soft: #f3dedf;
      --amber: #9a5b00;
      --amber-soft: #f4ead5;
      --violet: #5d43a0;
      --violet-soft: #e7e1f3;
      --blue: #1f63ad;
      --blue-soft: #dde8f5;
      --shadow: 0 16px 42px rgba(21, 24, 20, 0.10);
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,255,255,0) 300px),
        repeating-linear-gradient(90deg, rgba(21,24,20,0.028), rgba(21,24,20,0.028) 1px, transparent 1px, transparent 72px),
        var(--bg);
    }
    button, input, select, textarea { font: inherit; }
    button { cursor: pointer; }
    button:disabled {
      cursor: not-allowed;
      opacity: .52;
      transform: none !important;
    }
    .shell { max-width: 1600px; margin: 0 auto; padding: 24px; }
    .topbar {
      display: flex;
      align-items: stretch;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 16px;
    }
    .brand {
      display: flex;
      gap: 14px;
      align-items: center;
      min-width: 0;
    }
    .mark {
      width: 46px;
      height: 46px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background:
        linear-gradient(135deg, var(--green) 0 38%, var(--amber) 38% 62%, var(--violet) 62% 100%);
      box-shadow: inset 0 0 0 4px rgba(255,255,255,0.65);
      flex: 0 0 auto;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(24px, 3vw, 42px); line-height: 1; letter-spacing: 0; }
    h2 { font-size: 19px; line-height: 1.2; letter-spacing: 0; }
    h3 { font-size: 14px; line-height: 1.25; letter-spacing: 0; }
    .subtle { color: var(--muted); font-size: 13px; line-height: 1.45; }
    .run-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(88px, 1fr));
      gap: 8px;
      min-width: 430px;
    }
    .run-tile {
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
      border-radius: 8px;
      padding: 10px 11px;
      min-height: 58px;
    }
    .tile-label {
      color: var(--faint);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 5px;
    }
    .tile-value { font-size: 18px; font-weight: 760; line-height: 1.05; }
    .nav {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin: 0 0 16px;
      padding: 9px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(245,246,241,0.92);
      backdrop-filter: blur(18px);
    }
    .nav button, .seg button, .chip, .small-btn, .icon-btn {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      min-height: 34px;
      padding: 7px 11px;
      transition: background .15s ease, border-color .15s ease, transform .15s ease;
    }
    .nav button:hover, .seg button:hover, .chip:hover, .small-btn:hover, .icon-btn:hover {
      border-color: var(--line-strong);
      transform: translateY(-1px);
    }
    .nav button.active, .seg button.active, .chip.active {
      color: #fff;
      background: var(--ink);
      border-color: var(--ink);
    }
    .nav-spacer { flex: 1 1 auto; }
    .lens-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .seg {
      display: flex;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      flex-wrap: wrap;
    }
    .seg button {
      border: 0;
      min-height: 29px;
      padding: 6px 9px;
      background: transparent;
      color: var(--muted);
    }
    .seg button.active { color: #fff; background: var(--ink); }

    .grid { display: grid; gap: 12px; }
    .overview-grid {
      grid-template-columns: minmax(290px, .88fr) minmax(420px, 1.35fr) minmax(280px, .8fr);
      align-items: start;
    }
    .two-col { grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr); align-items: start; }
    .three-col { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,0.94);
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .panel.flat { box-shadow: none; background: rgba(255,255,255,0.7); }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 16px 18px 12px;
      border-bottom: 1px solid var(--line);
      flex-wrap: wrap;
      background: linear-gradient(180deg, rgba(247,248,244,.78), rgba(255,255,255,.92));
    }
    .panel-body { padding: 16px 18px 18px; }
    .metric-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      padding: 10px 0;
      border-bottom: 1px solid rgba(217,223,210,.72);
    }
    .metric-row:last-child { border-bottom: 0; }
    .rank-card {
      display: grid;
      gap: 9px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      margin-bottom: 9px;
    }
    .rank-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: start;
    }
    .rank-name {
      display: flex;
      gap: 9px;
      align-items: center;
      min-width: 0;
    }
    .swatch { width: 10px; height: 28px; border-radius: 4px; flex: 0 0 auto; }
    .rank-title { font-weight: 760; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .score-pill {
      min-width: 58px;
      text-align: center;
      border-radius: 999px;
      padding: 5px 8px;
      background: var(--green-soft);
      color: var(--green);
      font-weight: 760;
      font-size: 12px;
    }
    .score-pill.amber { background: var(--amber-soft); color: var(--amber); }
    .score-pill.red { background: var(--red-soft); color: var(--red); }
    .score-pill.violet { background: var(--violet-soft); color: var(--violet); }
    .why { color: var(--muted); font-size: 12px; line-height: 1.35; }
    .stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 8px; }
    .stat {
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      min-width: 0;
    }
    .stat .value { font-size: 22px; font-weight: 780; line-height: 1.05; margin-top: 4px; }
    .pos { color: var(--green); }
    .neg { color: var(--red); }
    .neutral { color: var(--muted); }
    .chart {
      width: 100%;
      height: 330px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background:
        linear-gradient(180deg, rgba(255,255,255,.96), rgba(248,250,246,.96)),
        #fff;
      overflow: hidden;
    }
    .chart.tall { height: 420px; }
    .chart.short { height: 230px; }
    .chart.micro { height: 160px; }
    svg text { font-family: inherit; letter-spacing: 0; }
    .axis { fill: var(--faint); font-size: 10px; }
    .grid-line { stroke: rgba(98,105,97,0.14); stroke-width: 1; }
    .line-path { fill: none; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
    .compare-path { filter: drop-shadow(0 1px 0 rgba(255,255,255,.75)); }
    .bench-path { stroke-dasharray: 4 4; opacity: .72; }
    .point { stroke: #fff; stroke-width: 1.7; }
    .label {
      fill: var(--ink);
      font-size: 11px;
      font-weight: 760;
      paint-order: stroke fill;
      stroke: #fff;
      stroke-width: 3px;
      stroke-linejoin: round;
    }
    .compare-strip, .sector-strip, .filter-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.2;
      white-space: nowrap;
    }
    .chip-dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: currentColor;
    }
    .table-wrap {
      width: 100%;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 900px;
    }
    th, td {
      padding: 9px 10px;
      border-bottom: 1px solid rgba(217,223,210,.82);
      text-align: right;
      font-size: 12px;
      line-height: 1.25;
    }
    td { white-space: nowrap; }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f7f8f3;
      color: var(--muted);
      font-weight: 740;
      cursor: pointer;
      white-space: normal;
      vertical-align: bottom;
    }
    tbody tr:nth-child(even) td { background: #fbfcf8; }
    th:first-child, td:first-child { text-align: left; position: sticky; left: 0; background: #fff; z-index: 2; }
    tbody tr:nth-child(even) td:first-child { background: #fbfcf8; }
    th:first-child { z-index: 3; background: #f7f8f3; }
    tr:hover td { background: rgba(224,238,240,.45); }
    tr:hover td:first-child { background: rgba(224,238,240,.72); }
    .ticker-cell { display: flex; align-items: center; gap: 8px; min-width: 150px; }
    .mono { font-variant-numeric: tabular-nums; }
    .mini-bars { display: grid; gap: 8px; }
    .mini-bar {
      display: grid;
      grid-template-columns: minmax(86px, 140px) minmax(0, 1fr) 70px;
      gap: 8px;
      align-items: center;
      font-size: 12px;
    }
    .bar-track {
      height: 10px;
      border-radius: 999px;
      background: #edf0e8;
      overflow: hidden;
      position: relative;
    }
    .bar-fill {
      height: 100%;
      border-radius: 999px;
      background: var(--green);
    }
    .split-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .list-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      padding: 8px 0;
      border-bottom: 1px solid rgba(217,223,210,.82);
      font-size: 12px;
    }
    .list-row:last-child { border-bottom: 0; }
    .sector-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 12px; align-items: start; }
    .sector-list {
      display: grid;
      gap: 6px;
      position: sticky;
      top: 82px;
    }
    .sector-btn {
      display: grid;
      grid-template-columns: 10px minmax(0,1fr) auto;
      align-items: center;
      gap: 8px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 9px;
      text-align: left;
    }
    .sector-btn.active { border-color: var(--ink); box-shadow: inset 0 0 0 1px var(--ink); }
    .sector-btn .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 700; }
    .compare-layout { display: grid; gap: 12px; }
    .compare-toolbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: start;
      margin-bottom: 12px;
    }
    .compare-selector {
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      align-items: center;
    }
    .compare-legend {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }
    .series-key {
      display: grid;
      grid-template-columns: 46px minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      min-height: 42px;
      padding: 8px 9px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.2;
    }
    .series-key strong {
      display: block;
      color: var(--ink);
      overflow: visible;
      text-overflow: clip;
      white-space: normal;
    }
    .series-key .series-label { min-width: 0; }
    .series-key .meta {
      color: var(--faint);
      font-size: 11px;
      white-space: nowrap;
    }
    .series-spark {
      width: 44px;
      height: 14px;
      overflow: visible;
    }
    .series-spark line {
      stroke-width: 3.2;
      stroke-linecap: round;
    }
    .compare-table table { min-width: 1040px; }
    .compare-chart { height: 440px; }
    .drawer {
      position: fixed;
      inset: 0 0 0 auto;
      width: min(460px, 100vw);
      z-index: 50;
      background: #fff;
      border-left: 1px solid var(--line-strong);
      box-shadow: -20px 0 60px rgba(25,27,24,.16);
      transform: translateX(100%);
      transition: transform .18s ease;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    .drawer.open { transform: translateX(0); }
    .drawer-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      padding: 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-soft);
    }
    .drawer-body { padding: 18px; overflow: auto; }
    .input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      min-height: 36px;
      padding: 8px 10px;
      color: var(--ink);
    }
    textarea { resize: vertical; line-height: 1.4; }
    .quality-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; }
    .quality-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      padding: 11px;
    }
    .warning {
      border-left: 4px solid var(--amber);
      padding: 9px 10px;
      background: var(--amber-soft);
      border-radius: 6px;
      font-size: 12px;
      line-height: 1.35;
    }
    .empty {
      min-height: 120px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line-strong);
      border-radius: 8px;
      background: var(--panel-soft);
    }
    .footnote { font-size: 11px; color: var(--faint); line-height: 1.4; }
    .setup-grid { display: grid; grid-template-columns: minmax(280px, .75fr) minmax(0, 1.25fr); gap: 12px; align-items: start; }
    .primary-btn {
      border: 1px solid var(--ink);
      border-radius: 8px;
      background: var(--ink);
      color: #fff;
      min-height: 42px;
      padding: 10px 14px;
      font-weight: 760;
    }
    .pending-note {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--amber);
      border-radius: 8px;
      background: var(--amber-soft);
      color: var(--amber);
      padding: 9px 10px;
      font-size: 12px;
      font-weight: 720;
    }
    .refresh-options {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      padding: 10px;
    }
    .refresh-options summary {
      cursor: pointer;
      font-size: 12px;
      font-weight: 760;
      color: var(--muted);
    }
    .refresh-options .compare-strip { margin-top: 10px; }
    .candidate-card {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 11px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .candidate-card + .candidate-card { margin-top: 8px; }
    .intake-panel {
      display: grid;
      grid-template-columns: minmax(300px, .8fr) minmax(0, 1.2fr);
      gap: 12px;
      align-items: start;
    }
    .intake-key-grid {
      display: grid;
      grid-template-columns: minmax(180px, 1fr) minmax(150px, .55fr) auto auto;
      gap: 8px;
      align-items: end;
    }
    .intake-status {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      font-size: 12px;
      color: var(--muted);
    }
    .intake-table { min-width: 980px; }
    .intake-table input[type="text"] {
      min-width: 150px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 7px 8px;
    }
    .path-pill {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 11px;
      line-height: 1.3;
    }
    .source-badges {
      display: flex;
      gap: 5px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 5px;
    }
    .source-badge {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 3px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 10px;
      font-weight: 760;
    }
    .source-badge.ok { color: var(--green); border-color: rgba(8,112,79,.3); background: var(--green-soft); }
    .source-badge.error { color: var(--red); border-color: rgba(178,58,58,.3); background: var(--red-soft); }
    .confidence-meter {
      width: 74px;
      height: 8px;
      border-radius: 999px;
      background: var(--line);
      overflow: hidden;
      margin-top: 5px;
    }
    .confidence-meter span { display: block; height: 100%; background: var(--green); }
    .coverage-dots { display: flex; gap: 5px; align-items: center; flex-wrap: wrap; margin-top: 7px; }
    .coverage-dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--line-strong);
      border: 1px solid rgba(25,27,24,.08);
    }
    .coverage-dot.good { background: var(--green); }
    .run-log {
      max-height: 260px;
      overflow: auto;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #121411;
      color: #e9efe1;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 11px;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    .heatmap-table {
      display: grid;
      gap: 4px;
      overflow: auto;
    }
    .heatmap-row {
      display: grid;
      grid-template-columns: minmax(82px, 118px) repeat(var(--cols), minmax(70px, 1fr));
      gap: 4px;
      align-items: stretch;
      min-width: 760px;
    }
    .heatmap-cell {
      min-height: 36px;
      border-radius: 6px;
      padding: 7px 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      font-size: 11px;
      font-weight: 720;
      color: var(--ink);
      border: 1px solid rgba(25,27,24,.06);
      line-height: 1.15;
    }
    .heatmap-label {
      justify-content: flex-start;
      background: var(--panel-soft);
      color: var(--muted);
      font-weight: 760;
    }
    .heatmap-reference {
      display: grid;
      gap: 8px;
      margin-top: 10px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
    }
    .legend-row {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }
    .legend-chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      font-weight: 700;
    }
    .legend-swatch {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      border: 1px solid rgba(25,27,24,.08);
    }
    .reference-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 6px 12px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }
    .rank-summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }
    .metric-tags {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      align-items: center;
    }
    .metric-tag, .coverage-badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 7px;
      border: 1px solid var(--line);
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      line-height: 1.2;
    }
    .coverage-badge.good { color: var(--green); background: var(--green-soft); }
    .coverage-badge.warn { color: var(--amber); background: var(--amber-soft); }
    .coverage-badge.bad { color: var(--red); background: var(--red-soft); }
    .cycle-badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      border-radius: 999px;
      padding: 3px 8px;
      border: 1px solid var(--line);
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 11px;
      font-weight: 760;
      line-height: 1.2;
      white-space: nowrap;
    }
    .cycle-badge.hot { color: var(--green); background: var(--green-soft); border-color: rgba(8,112,79,.26); }
    .cycle-badge.cold { color: var(--blue); background: var(--blue-soft); border-color: rgba(40,111,177,.26); }
    .cycle-badge.warning { color: var(--amber); background: var(--amber-soft); border-color: rgba(167,102,20,.26); }
    .cycle-badge.extreme { color: var(--violet); background: var(--violet-soft); border-color: rgba(104,77,163,.26); }
    .cycle-badge.bad { color: var(--red); background: var(--red-soft); border-color: rgba(178,58,58,.26); }
    .mrr-input-panel {
      display: grid;
      gap: 11px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
      margin-bottom: 12px;
    }
    .mrr-input-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: start;
      flex-wrap: wrap;
    }
    .mrr-input-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }
    .mrr-input-group {
      display: grid;
      gap: 6px;
      align-content: start;
    }
    .mrr-input-group h3 {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .mrr-toggle {
      width: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 5px 8px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 8px 9px;
      text-align: left;
    }
    .mrr-toggle.active {
      border-color: var(--green);
      box-shadow: inset 0 0 0 1px rgba(8,112,79,.24);
      background: var(--green-soft);
    }
    .mrr-toggle.pending {
      border-style: dashed;
      border-color: var(--amber);
    }
    .mrr-toggle .metric-name {
      font-weight: 760;
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .metric-dir {
      border-radius: 999px;
      padding: 2px 6px;
      background: rgba(255,255,255,.8);
      color: var(--muted);
      border: 1px solid var(--line);
      font-size: 10px;
      font-weight: 760;
      line-height: 1.2;
    }
    .metric-availability {
      grid-column: 1 / -1;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.25;
    }
    .mrr-receipt {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }
    .mrr-active-tape {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      padding: 2px 0;
    }
    .mrr-active-tape span {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 3px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,.6);
      color: var(--muted);
      font-size: 10px;
      font-weight: 760;
      line-height: 1.2;
      white-space: nowrap;
    }
    .mrr-status {
      display: grid;
      gap: 4px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .mrr-status strong { color: var(--ink); }
    .mrr-status.pending {
      border-color: var(--amber);
      background: var(--amber-soft);
    }
    .mrr-status.calculating {
      border-color: var(--blue);
      background: var(--blue-soft);
    }
    .mrr-status.current {
      border-color: rgba(8,112,79,.32);
      background: var(--green-soft);
    }
    .mrr-status.error {
      border-color: var(--red);
      background: var(--red-soft);
    }
    .mrr-flash {
      animation: mrrPulse .9s ease;
    }
    .mrr-dist-chart {
      height: 300px;
      background:
        radial-gradient(circle at 78% 18%, rgba(8,112,79,.10), transparent 32%),
        linear-gradient(180deg, rgba(255,255,255,.92), rgba(251,251,247,.92)),
        #fff;
    }
    .mrr-distribution-panel {
      display: grid;
      gap: 12px;
      margin-bottom: 12px;
      padding: 13px;
      border: 1px solid color-mix(in srgb, var(--green) 28%, var(--line));
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(223,238,231,.86), rgba(255,255,255,.84) 42%, rgba(224,238,240,.72)),
        var(--panel-soft);
      overflow: hidden;
    }
    .mrr-distribution-head {
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .mrr-distribution-layout {
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
      gap: 12px;
      align-items: stretch;
    }
    .mrr-dist-stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      align-content: start;
    }
    .mrr-dist-stat {
      min-height: 74px;
      padding: 10px;
      border: 1px solid rgba(8,112,79,.16);
      border-radius: 8px;
      background: rgba(255,255,255,.72);
    }
    .mrr-dist-stat .value {
      margin-top: 4px;
      font-size: 25px;
      line-height: 1;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }
    .mrr-dist-note {
      grid-column: 1 / -1;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.4;
    }
    .candidate-workbench {
      display: grid;
      gap: 12px;
    }
    .candidate-cockpit {
      display: grid;
      grid-template-columns: minmax(0, 1.22fr) minmax(360px, .78fr);
      gap: 12px;
      align-items: start;
    }
    .candidate-command-bar {
      position: sticky;
      top: 74px;
      z-index: 8;
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: color-mix(in srgb, var(--panel) 90%, transparent);
      backdrop-filter: blur(12px);
    }
    .candidate-table-shell {
      display: grid;
      gap: 8px;
    }
    .candidate-table-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: end;
      flex-wrap: wrap;
    }
    .candidate-table-head h3 {
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .dist-bar {
      opacity: .84;
      transition: opacity .15s ease;
    }
    .dist-bar:hover { opacity: 1; }
    .dist-curve {
      fill: none;
      stroke: var(--teal);
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .dist-fill {
      fill: color-mix(in srgb, var(--teal-soft) 74%, transparent);
      opacity: .72;
    }
    .dist-marker {
      stroke-width: 1.4;
      stroke-dasharray: 4 4;
    }
    .dist-marker-label {
      fill: var(--muted);
      font-size: 10px;
      font-weight: 740;
    }
    .dist-band-label {
      fill: var(--green);
      font-size: 10px;
      font-weight: 780;
    }
    @keyframes mrrPulse {
      0% { box-shadow: inset 0 0 0 999px rgba(8,112,79,.12); }
      100% { box-shadow: inset 0 0 0 0 rgba(8,112,79,0); }
    }

    @media (max-width: 1180px) {
      .overview-grid, .two-col, .three-col, .quality-grid, .setup-grid, .rank-summary, .mrr-distribution-layout, .candidate-cockpit, .intake-panel, .intake-key-grid { grid-template-columns: 1fr; }
      .run-strip { min-width: 0; grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .sector-layout { grid-template-columns: 1fr; }
      .sector-list { position: static; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 720px) {
      .shell { padding: 14px; }
      .topbar { flex-direction: column; }
      .run-strip { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .stat-grid, .split-list { grid-template-columns: 1fr; }
      .chart, .chart.tall { height: 300px; }
      .mini-bar { grid-template-columns: 84px minmax(0, 1fr) 54px; }
      .sector-list { grid-template-columns: 1fr; }
      .series-key { grid-template-columns: 46px minmax(0, 1fr); }
      .series-key > .meta {
        grid-column: 2;
        justify-self: start;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark" aria-hidden="true"></div>
        <div>
          <h1>Market Basket Analyst Workstation</h1>
          <p class="subtle" id="range-copy">Cross-sector rotation, setup quality, positioning, fundamentals, and data confidence.</p>
        </div>
      </div>
      <div class="run-strip" id="run-strip"></div>
    </header>

    <nav class="nav">
      <button data-action="view" data-view="overview" class="active">Overview</button>
      <button data-action="view" data-view="compare">Compare</button>
      <button data-action="view" data-view="sector">Sector</button>
      <button data-action="view" data-view="tickers">Candidates</button>
      <button data-action="view" data-view="portfolio-review">Portfolio Review</button>
      <button data-action="view" data-view="setup">Run & Universe</button>
      <button data-action="view" data-view="data">Data</button>
      <div class="nav-spacer"></div>
      <div class="lens-wrap">
        <span class="tile-label">Capital lens</span>
        <div class="seg" id="lens-controls"></div>
      </div>
    </nav>

    <main id="view-root"></main>
  </div>

  <aside class="drawer" id="ticker-drawer" aria-hidden="true"></aside>

  <script id="dashboard-data" type="application/json">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
    const lensDefs = [
      { id: "balanced", label: "Balanced", score: "balancedScore" },
      { id: "momentum", label: "Leadership", score: "momentumScore" },
      { id: "rebound", label: "Rebound", score: "pullbackScore" },
      { id: "squeeze", label: "Squeeze", score: "squeezeScore" },
      { id: "sponsor", label: "Sponsor", score: "institutionalScore" },
      { id: "quality", label: "Quality", score: "qualityScore" },
      { id: "torque", label: "Torque", score: "torqueScore" }
    ];
    const benchmarks = [
      { id: "SPY", label: "SPY", color: "#636a60" },
      { id: "QQQ", label: "QQQ", color: "#286fb1" },
      { id: "BTC-USD", label: "BTC", color: "#a76614" }
    ];
    const compareStyleByBasket = {
      photonics: { color: "#E69F00", dash: "" },
      semiconductors: { color: "#0072B2", dash: "8 4" },
      btc_mining_ai_pivot: { color: "#CC79A7", dash: "2 5" },
      oil_tankers: { color: "#009E73", dash: "10 4 2 4" },
      rare_earth_minerals: { color: "#D55E00", dash: "1 5" },
      metals: { color: "#4D5656", dash: "12 4" },
      oil: { color: "#117733", dash: "5 3 1 3" },
      fertilizer: { color: "#7A8B00", dash: "14 5 3 5" },
      power_grid: { color: "#1876A6", dash: "3 4" },
      cybersecurity: { color: "#332288", dash: "9 3" },
      construction: { color: "#B34D00", dash: "6 2 2 2" },
      quantum: { color: "#882255", dash: "2 3 8 3" },
      software: { color: "#117A78", dash: "4 2" },
      crypto: { color: "#996600", dash: "11 3 2 3" }
    };
    const fallbackCompareColors = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#332288", "#E69F00", "#117A78", "#882255"];
    const fallbackCompareDashes = ["", "8 4", "2 5", "10 4 2 4", "1 5", "12 4", "5 3 1 3", "4 2"];
    function compareStyleForBasket(id, index = 0) {
      const style = compareStyleByBasket[id] || {};
      return {
        color: style.color || fallbackCompareColors[index % fallbackCompareColors.length],
        dash: style.dash ?? fallbackCompareDashes[index % fallbackCompareDashes.length],
        strokeWidth: 3.2
      };
    }
    const seriesPreview = (color, dash = "") => `
      <svg class="series-spark" viewBox="0 0 44 14" aria-hidden="true">
        <line x1="2" x2="42" y1="7" y2="7" stroke="${color}" ${dash ? `stroke-dasharray="${dash}"` : ""}></line>
      </svg>
    `;
    const dashName = dash => dash ? "patterned" : "solid";
    const state = {
      view: "overview",
      lens: "balanced",
      selectedBaskets: new Set(DATA.metrics.slice().sort((a, b) => b.returnPct - a.returnPct).slice(0, 5).map(d => d.basket)),
      selectedSector: DATA.metrics.slice().sort((a, b) => b.returnPct - a.returnPct)[0]?.basket,
      compareSort: "balancedScore",
      compareDir: "desc",
      sectorSort: "candidateScore",
      sectorDir: "desc",
      sectorFilter: "all",
      tickerSort: "candidateScore",
      tickerDir: "desc",
      tickerFilter: "all",
      tickerSector: "all",
      tickerSearch: "",
      tickerLens: "momentum",
      candidateMode: "balanced",
      candidateActiveMetricIds: [],
      candidateDraftMetricIds: [],
      candidateInputsDirty: false,
      candidateInputMessage: "",
      candidateCalcStatus: "current",
      candidateCalcVersion: 1,
      candidateLastCalcAt: "page load",
      candidateLastCalcRows: 0,
      candidateVisibleRowCount: 0,
      showMrrDistribution: true,
      openTicker: null,
      showBenchmarks: new Set(["SPY", "QQQ"]),
      setupAvailable: false,
      setupState: null,
      setupCategory: DATA.metrics[0]?.basket || "",
      setupSearch: "",
      setupResults: [],
      setupMessage: "",
      intakeText: "",
      intakeRows: [],
      intakeMessage: "",
      intakeBusy: false,
      openaiStatus: null,
      openaiModel: "gpt-5.4-nano",
      portfolioReview: null,
      portfolioReviewMessage: "",
      portfolioReviewBusy: false,
      portfolioReviewGoal: 1.0,
      portfolioReviewRefreshData: false,
      portfolioImportText: "",
      portfolioImportId: "uploaded_portfolio",
      portfolioImportMessage: "",
      pendingChanges: false,
      runStatus: null,
      refreshPrices: false,
      refreshFundamentals: false,
      refreshPositioning: false,
      refreshOwnership: false
    };

    const isNum = v => typeof v === "number" && Number.isFinite(v);
    const clamp = (v, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, v));
    const avg = vals => {
      const xs = vals.filter(isNum);
      return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
    };
    const quantile = (values, q) => {
      const xs = values.filter(isNum).slice().sort((a, b) => a - b);
      if (!xs.length) return null;
      const pos = (xs.length - 1) * clamp(q, 0, 1);
      const base = Math.floor(pos);
      const rest = pos - base;
      return xs[base + 1] !== undefined ? xs[base] + rest * (xs[base + 1] - xs[base]) : xs[base];
    };
    const fmtPct = v => isNum(v) ? `${v >= 0 ? "+" : ""}${v.toFixed(v === 0 ? 0 : Math.abs(v) >= 10 ? 1 : 2)}%` : "n/a";
    const fmtNum = v => isNum(v) ? v.toLocaleString(undefined, { maximumFractionDigits: Math.abs(v) >= 100 ? 0 : 1 }) : "n/a";
    const fmtPctile = v => isNum(v) ? `${v.toFixed(0)}p` : "n/a";
    const cls = v => !isNum(v) || Math.abs(v) < 0.01 ? "neutral" : v > 0 ? "pos" : "neg";
    const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    const pctRank = (items, key, value, invert = false, transform = x => x) => {
      if (!isNum(value)) return null;
      const vals = items.map(d => transform(d[key])).filter(isNum).sort((a, b) => a - b);
      if (!vals.length) return null;
      const val = transform(value);
      if (!isNum(val)) return null;
      let idx = vals.findIndex(x => x >= val);
      if (idx < 0) idx = vals.length - 1;
      const score = vals.length === 1 ? 100 : (idx / (vals.length - 1)) * 100;
      return invert ? 100 - score : score;
    };
    const candidateMetricCatalog = [
      { id: "return_total", key: "returnPct", label: "Total Return", group: "Performance", direction: "desc", directionLabel: "higher ranks better" },
      { id: "return_20d", key: "return20dPct", label: "20D Return", group: "Performance", direction: "desc", directionLabel: "higher ranks better" },
      { id: "return_5d", key: "return5dPct", label: "5D Return", group: "Performance", direction: "desc", directionLabel: "higher ranks better" },
      { id: "return_vol", key: "returnVolRatio", label: "Return / Volatility", group: "Risk", direction: "desc", directionLabel: "higher ranks better" },
      { id: "drawdown_control", key: "currentDrawdownPct", label: "Drawdown Control", group: "Risk", direction: "desc", directionLabel: "higher ranks better", note: "less negative drawdown ranks better" },
      { id: "pullback_depth", key: "currentDrawdownPct", label: "Pullback Depth", group: "Contrarian", direction: "asc", directionLabel: "lower ranks better", note: "deeper negative drawdown ranks better" },
      { id: "rebound_low", key: "reboundFromLowPct", label: "Rebound From Low", group: "Trend", direction: "desc", directionLabel: "higher ranks better" },
      { id: "volatility_low", key: "annualizedVolPct", label: "Lower Volatility", group: "Risk", direction: "asc", directionLabel: "lower ranks better" },
      { id: "volatility_high", key: "annualizedVolPct", label: "Volatility Expansion", group: "Speculation", direction: "desc", directionLabel: "higher ranks better" },
      { id: "short_float", key: "shortPctFloat", label: "Short Interest % Float", group: "Positioning", direction: "desc", directionLabel: "higher ranks better" },
      { id: "days_to_cover", key: "daysToCover", label: "Days To Cover", group: "Positioning", direction: "desc", directionLabel: "higher ranks better" },
      { id: "short_volume", key: "shortVolumeRatioPct", label: "Short Volume Share", group: "Positioning", direction: "desc", directionLabel: "higher ranks better" },
      { id: "put_call_oi", key: "putCallOpenInterestRatio", label: "Put / Call Open Interest", group: "Options", direction: "desc", directionLabel: "higher ranks better" },
      { id: "put_call_volume", key: "putCallVolumeRatio", label: "Put / Call Volume", group: "Options", direction: "desc", directionLabel: "higher ranks better" },
      { id: "options_iv", key: "optionsIvPct", label: "Options Implied Volatility", group: "Options", direction: "desc", directionLabel: "higher ranks better" },
      { id: "institutional_change", key: "institutionalSharesChangedQoqPct", label: "Institutional Shares Change", group: "Ownership", direction: "desc", directionLabel: "higher ranks better" },
      { id: "institutional_ownership", key: "institutionalOwnershipPct", label: "Institutional Ownership", group: "Ownership", direction: "desc", directionLabel: "higher ranks better" },
      { id: "institutional_count", key: "institutionalInvestorCount", label: "Institutional Investor Count", group: "Ownership", direction: "desc", directionLabel: "higher ranks better" },
      { id: "free_cash_flow_margin", key: "freeCashFlowMarginPct", label: "Free Cash Flow Margin", group: "Quality", direction: "desc", directionLabel: "higher ranks better" },
      { id: "operating_margin", key: "operatingMarginPct", label: "Operating Margin", group: "Quality", direction: "desc", directionLabel: "higher ranks better" },
      { id: "gross_margin", key: "grossMarginPct", label: "Gross Margin", group: "Quality", direction: "desc", directionLabel: "higher ranks better" },
      { id: "revenue_growth", key: "revenueGrowthYoyPct", label: "Revenue Growth", group: "Quality", direction: "desc", directionLabel: "higher ranks better" },
      { id: "net_cash", key: "netCash", label: "Net Cash", group: "Balance Sheet", direction: "desc", directionLabel: "higher ranks better" },
      { id: "data_coverage", key: "coverageScore", label: "Data Coverage", group: "Confidence", direction: "desc", directionLabel: "higher ranks better" },
      { id: "cycle_extreme", key: "technicalExtremeScore", label: "Cycle Extreme Score", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better", note: "farther from this ticker's own technical history ranks higher" },
      { id: "cycle_heat", key: "technicalHeatScore", label: "Technical Heat", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better", note: "upper-tail RSI, Stoch RSI, range, DMA stretch, and Bollinger position" },
      { id: "cycle_washout", key: "technicalWashoutScore", label: "Technical Washout", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better", note: "lower-tail mirror of the heat score" },
      { id: "rsi_percentile_high", key: "rsi14Percentile", label: "RSI Percentile", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better", note: "current RSI versus this ticker's own RSI history" },
      { id: "rsi_percentile_low", key: "rsi14Percentile", label: "Low RSI Percentile", group: "Cycle / Technicals", direction: "asc", directionLabel: "lower ranks better", note: "low current RSI versus this ticker's own RSI history" },
      { id: "stoch_rsi_percentile_high", key: "stochRsi14Percentile", label: "Stoch RSI Percentile", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better" },
      { id: "dma_stretch_z", key: "distanceFrom20dmaZscore", label: "20DMA Stretch Z", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better" },
      { id: "return_5d_z", key: "return5dZscore", label: "5D Return Z", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better" },
      { id: "volume_z", key: "volumeZscore20d", label: "Volume Z", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better" },
      { id: "realized_vol_pctile", key: "realizedVol20dPercentile", label: "Realized Vol Percentile", group: "Cycle / Technicals", direction: "desc", directionLabel: "higher ranks better" }
    ];
    const candidateMetricById = new Map(candidateMetricCatalog.map(metric => [metric.id, metric]));
    const candidateModeDefs = {
      balanced: {
        label: "Balanced",
        description: "MRR across performance, risk control, positioning, sponsorship, quality, and data coverage.",
        metricIds: ["return_total", "return_20d", "return_vol", "drawdown_control", "rebound_low", "institutional_change", "free_cash_flow_margin", "revenue_growth", "data_coverage"]
      },
      momentum: {
        label: "Momentum",
        description: "MRR for names repeatedly ranking near the top on recent and full-window performance.",
        metricIds: ["return_total", "return_20d", "return_5d", "return_vol", "rebound_low", "drawdown_control"]
      },
      contrarian: {
        label: "Contrarian",
        description: "MRR for beaten-up names with early improvement, sponsorship, or quality support.",
        metricIds: ["pullback_depth", "rebound_low", "return_5d", "short_float", "short_volume", "institutional_change", "revenue_growth"]
      },
      squeeze: {
        label: "Squeeze",
        description: "MRR for high short pressure plus improving tape and option attention.",
        metricIds: ["short_float", "days_to_cover", "short_volume", "put_call_oi", "options_iv", "return_5d", "return_20d"]
      },
      quality: {
        label: "Quality",
        description: "MRR for fundamental durability, sponsorship, and risk discipline.",
        metricIds: ["free_cash_flow_margin", "operating_margin", "gross_margin", "revenue_growth", "net_cash", "institutional_ownership", "institutional_change", "drawdown_control"]
      },
      cycle: {
        label: "Cycle",
        description: "MRR for names whose RSI, range position, DMA stretch, volume, or volatility are abnormal versus their own history.",
        metricIds: ["cycle_extreme", "rsi_percentile_high", "stoch_rsi_percentile_high", "dma_stretch_z", "return_5d_z", "volume_z", "realized_vol_pctile"]
      }
    };
    const candidateModeList = Object.entries(candidateModeDefs);
    const modeMetricIds = modeId => {
      const mode = candidateModeDefs[modeId] || candidateModeDefs.balanced;
      return mode.metricIds.filter(id => candidateMetricById.has(id));
    };
    const metricIdsToMetrics = ids => ids.map(id => candidateMetricById.get(id)).filter(Boolean);
    const sameMetricIds = (a, b) => a.length === b.length && a.every(id => b.includes(id)) && b.every(id => a.includes(id));
    const calcTime = () => new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    function resetMrrInputs(modeId = state.candidateMode) {
      const ids = modeMetricIds(modeId);
      state.candidateActiveMetricIds = [...ids];
      state.candidateDraftMetricIds = [...ids];
      state.candidateInputsDirty = false;
      state.candidateInputMessage = "";
    }
    resetMrrInputs("balanced");
    const activeCandidateMetrics = () => {
      const ids = state.candidateActiveMetricIds.length ? state.candidateActiveMetricIds : modeMetricIds(state.candidateMode);
      return metricIdsToMetrics(ids);
    };
    const draftCandidateMetrics = () => {
      const ids = state.candidateDraftMetricIds.length ? state.candidateDraftMetricIds : modeMetricIds(state.candidateMode);
      return metricIdsToMetrics(ids);
    };
    const candidateId = (row, index) => row.ticker || row.basket || `row-${index}`;
    const metricValue = (row, metric) => {
      const raw = row[metric.key];
      const value = metric.transform ? metric.transform(raw, row) : raw;
      return isNum(value) ? value : null;
    };
    const metricRankLabel = rank => Number.isInteger(rank) ? `#${rank}` : `#${rank.toFixed(1)}`;
    function rankCandidateRows(rows, modeId = state.candidateMode) {
      const metrics = activeCandidateMetrics();
      const rankedRows = rows.map((row, index) => ({ ...row, candidateSourceIndex: index }));
      const records = new Map(rankedRows.map((row, index) => [candidateId(row, index), { reciprocal: 0, available: 0, leaders: [] }]));
      metrics.forEach(metric => {
        const metricRows = rankedRows
          .map((row, index) => ({ row, index, id: candidateId(row, index), value: metricValue(row, metric) }))
          .filter(item => isNum(item.value))
          .sort((a, b) => metric.direction === "asc" ? a.value - b.value : b.value - a.value);
        let i = 0;
        while (i < metricRows.length) {
          let j = i;
          while (j + 1 < metricRows.length && Math.abs(metricRows[j + 1].value - metricRows[i].value) < 1e-9) j += 1;
          const rank = ((i + 1) + (j + 1)) / 2;
          for (let k = i; k <= j; k += 1) {
            const item = metricRows[k];
            const record = records.get(item.id);
            record.reciprocal += 1 / rank;
            record.available += 1;
            record.leaders.push({ label: metric.label, group: metric.group, rank });
          }
          i = j + 1;
        }
      });
      rankedRows.forEach((row, index) => {
        const record = records.get(candidateId(row, index));
        row.candidateMetricCount = metrics.length;
        row.candidateAvailableMetrics = record.available;
        row.candidateCoveragePct = metrics.length ? (record.available / metrics.length) * 100 : 0;
        row.candidateMrrRaw = metrics.length ? record.reciprocal / metrics.length : 0;
        row.candidateWhy = record.leaders
          .filter(item => item.rank <= 3)
          .sort((a, b) => a.rank - b.rank)
          .slice(0, 3)
          .map(item => `${item.label} ${metricRankLabel(item.rank)}`)
          .join(" | ") || `${record.available}/${metrics.length} rank inputs available`;
      });
      const maxRaw = Math.max(...rankedRows.map(row => row.candidateMrrRaw), 0);
      rankedRows.forEach(row => {
        const normalized = maxRaw > 0 ? (row.candidateMrrRaw / maxRaw) * 100 : 0;
        const coveragePenalty = 0.72 + 0.28 * (row.candidateCoveragePct / 100);
        row.candidateScore = normalized * coveragePenalty;
      });
      rankedRows
        .sort((a, b) => (b.candidateScore - a.candidateScore) || ((b.returnPct ?? -9999) - (a.returnPct ?? -9999)))
        .forEach((row, index) => { row.candidateRank = index + 1; });
      return rankedRows;
    }
    const candidateModeButtons = () => `<div class="seg">${candidateModeList.map(([id, mode]) => `<button class="${state.candidateMode === id ? "active" : ""}" data-action="rank-mode" data-mode="${id}">${mode.label}</button>`).join("")}</div>`;
    const coverageClass = value => !isNum(value) ? "bad" : value >= 80 ? "good" : value >= 55 ? "warn" : "bad";
    const coverageBadge = value => `<span class="coverage-badge ${coverageClass(value)}">${isNum(value) ? value.toFixed(0) : "0"}% inputs</span>`;
    const cycleBadge = stateLabel => {
      const label = stateLabel || "n/a";
      const klass = /Extreme|Upper/.test(label) ? "hot" : /Washed|Lower/.test(label) ? "cold" : /Volatility|Compression/.test(label) ? "warning" : /Insufficient/.test(label) ? "bad" : "";
      return `<span class="cycle-badge ${klass}">${escapeHtml(label)}</span>`;
    };
    function markMrrCalculated(message) {
      state.candidateCalcStatus = "current";
      state.candidateCalcVersion += 1;
      state.candidateLastCalcAt = calcTime();
      state.candidateLastCalcRows = state.candidateVisibleRowCount || 0;
      state.candidateInputMessage = message || `MRR recalculated at ${state.candidateLastCalcAt} using ${state.candidateActiveMetricIds.length} inputs over ${state.candidateLastCalcRows} rows. Table, heatmap, rank, and why text were rebuilt.`;
    }
    const colorForScore = score => score >= 72 ? "score-pill" : score >= 50 ? "score-pill amber" : "score-pill red";
    const confidenceLabel = score => !isNum(score) ? "Unknown" : score >= 82 ? "High" : score >= 58 ? "Medium" : "Low";
    const stanceFor = m => {
      if (m.coverageScore < 45) return "Verify data";
      if (m.balancedScore >= 74 && m.riskControlScore >= 48) return "Press";
      if (m.pullbackScore >= 72 || m.torqueScore >= 72) return "Watch turn";
      if (m.qualityScore >= 70 && m.momentumScore >= 55) return "Compound";
      if (m.squeezeScore >= 72) return "Speculative";
      return "Monitor";
    };

    const rawBaskets = DATA.metrics.map(d => ({ ...d }));
    rawBaskets.forEach((m, index) => {
      const compareStyle = compareStyleForBasket(m.basket, index);
      m.displayColor = compareStyle.color;
      m.compareDash = compareStyle.dash;
      m.compareStrokeWidth = compareStyle.strokeWidth;
      m.coverageScore = avg([m.fundamentalsCoveragePct, m.optionsCoveragePct, m.shortInterestCoveragePct, m.institutionalCoveragePct]) ?? 0;
      m.recentBreadthPct = isNum(m.positive20dCount) && m.constituentsUsed ? (m.positive20dCount / m.constituentsUsed) * 100 : m.positivePct;
    });
    rawBaskets.forEach(m => {
      const sweetSpotDrawdown = 100 - Math.abs(Math.abs(m.currentDrawdownPct || 0) - 8) * 7;
      m.momentumScore = avg([
        pctRank(rawBaskets, "returnPct", m.returnPct),
        pctRank(rawBaskets, "return20dPct", m.return20dPct),
        pctRank(rawBaskets, "return5dPct", m.return5dPct),
        m.recentBreadthPct,
        pctRank(rawBaskets, "returnVolRatio", m.returnVolRatio)
      ]) ?? 0;
      m.pullbackScore = avg([
        clamp(sweetSpotDrawdown),
        pctRank(rawBaskets, "reboundFromLowPct", m.reboundFromLowPct),
        pctRank(rawBaskets, "return20dPct", m.return20dPct),
        m.recentBreadthPct,
        pctRank(rawBaskets, "annualizedVolPct", m.annualizedVolPct)
      ]) ?? 0;
      m.squeezeScore = avg([
        pctRank(rawBaskets, "shortPctFloat", m.shortPctFloat),
        pctRank(rawBaskets, "shortVolumeRatioPct", m.shortVolumeRatioPct),
        pctRank(rawBaskets, "optionsIvPct", m.optionsIvPct),
        pctRank(rawBaskets, "return20dPct", m.return20dPct),
        pctRank(rawBaskets, "reboundFromLowPct", m.reboundFromLowPct)
      ]) ?? 0;
      m.institutionalScore = avg([
        pctRank(rawBaskets, "institutionalSharesChangedQoqPct", m.institutionalSharesChangedQoqPct),
        pctRank(rawBaskets, "institutionalOwnershipPct", m.institutionalOwnershipPct),
        pctRank(rawBaskets, "institutionalInvestorCount", m.institutionalInvestorCount),
        m.institutionalCoveragePct
      ]) ?? 0;
      m.qualityScore = avg([
        pctRank(rawBaskets, "freeCashFlowMarginPct", m.freeCashFlowMarginPct),
        pctRank(rawBaskets, "operatingMarginPct", m.operatingMarginPct),
        pctRank(rawBaskets, "grossMarginPct", m.grossMarginPct),
        pctRank(rawBaskets, "revenueGrowthYoyPct", m.revenueGrowthYoyPct),
        pctRank(rawBaskets, "netCash", m.netCash)
      ]) ?? 0;
      m.riskControlScore = avg([
        pctRank(rawBaskets, "maxDrawdownPct", m.maxDrawdownPct, true, x => Math.abs(x || 0)),
        pctRank(rawBaskets, "annualizedVolPct", m.annualizedVolPct, true),
        pctRank(rawBaskets, "returnVolRatio", m.returnVolRatio),
        pctRank(rawBaskets, "returnDrawdownRatio", m.returnDrawdownRatio),
        m.coverageScore
      ]) ?? 0;
      m.torqueScore = avg([
        pctRank(rawBaskets, "annualizedVolPct", m.annualizedVolPct),
        pctRank(rawBaskets, "betaVsQqq", m.betaVsQqq),
        pctRank(rawBaskets, "shortPctFloat", m.shortPctFloat),
        pctRank(rawBaskets, "reboundFromLowPct", m.reboundFromLowPct),
        pctRank(rawBaskets, "return20dPct", m.return20dPct)
      ]) ?? 0;
      m.balancedScore = avg([
        m.momentumScore,
        m.qualityScore,
        m.institutionalScore,
        m.riskControlScore,
        m.coverageScore
      ]) ?? 0;
      m.stance = stanceFor(m);
    });
    const baskets = rawBaskets;
    const basketById = new Map(baskets.map(d => [d.basket, d]));
    const tickers = DATA.tickers.map(d => ({ ...d }));
    const tickersForScores = tickers;
    tickers.forEach(t => {
      t.returnVolRatio = isNum(t.returnPct) && isNum(t.annualizedVolPct) ? t.returnPct / Math.max(1, t.annualizedVolPct) : null;
      t.cycleScore = t.technicalExtremeScore ?? avg([t.technicalHeatScore, t.technicalWashoutScore]) ?? 0;
      t.coverageScore = avg([
        t.fundamentalsStatus ? 100 : 0,
        t.shortInterestStatus === "full" ? 100 : t.shortPctFloat != null ? 70 : 0,
        t.optionsStatus === "full" ? 100 : t.putCallOpenInterestRatio != null ? 70 : 0,
        t.institutionalStatus === "full" ? 100 : t.institutionalOwnershipPct != null ? 70 : 0
      ]) ?? 0;
    });
    tickers.forEach(t => {
      t.momentumScore = avg([
        pctRank(tickersForScores, "returnPct", t.returnPct),
        pctRank(tickersForScores, "return20dPct", t.return20dPct),
        pctRank(tickersForScores, "return5dPct", t.return5dPct),
        pctRank(tickersForScores, "returnVolRatio", t.returnPct / Math.max(1, t.annualizedVolPct))
      ]) ?? 0;
      t.squeezeScore = avg([
        pctRank(tickersForScores, "shortPctFloat", t.shortPctFloat),
        pctRank(tickersForScores, "shortVolumeRatioPct", t.shortVolumeRatioPct),
        pctRank(tickersForScores, "optionsIvPct", t.optionsIvPct),
        pctRank(tickersForScores, "return20dPct", t.return20dPct)
      ]) ?? 0;
      t.qualityScore = avg([
        pctRank(tickersForScores, "freeCashFlowMarginPct", t.freeCashFlowMarginPct),
        pctRank(tickersForScores, "operatingMarginPct", t.operatingMarginPct),
        pctRank(tickersForScores, "grossMarginPct", t.grossMarginPct),
        pctRank(tickersForScores, "revenueGrowthYoyPct", t.revenueGrowthYoyPct),
        pctRank(tickersForScores, "netCash", t.netCash)
      ]) ?? 0;
      t.reboundScore = avg([
        pctRank(tickersForScores, "reboundFromLowPct", t.reboundFromLowPct),
        pctRank(tickersForScores, "return20dPct", t.return20dPct),
        pctRank(tickersForScores, "annualizedVolPct", t.annualizedVolPct)
      ]) ?? 0;
    });
    const tickerBySymbol = new Map(tickers.map(t => [t.ticker, t]));

    function currentLens() {
      return lensDefs.find(l => l.id === state.lens) || lensDefs[0];
    }

    function topBy(scoreKey, n = 5) {
      return baskets.slice().sort((a, b) => (b[scoreKey] ?? -1) - (a[scoreKey] ?? -1)).slice(0, n);
    }

    function whyFor(m, lens = currentLens().id) {
      const parts = [];
      if (lens === "squeeze") {
        parts.push(`${fmtPct(m.shortPctFloat)} short float`);
        parts.push(`${fmtPct(m.shortVolumeRatioPct)} short volume`);
        parts.push(`${fmtPct(m.return20dPct)} 20D`);
      } else if (lens === "rebound" || lens === "torque") {
        parts.push(`${fmtPct(m.reboundFromLowPct)} rebound`);
        parts.push(`${fmtPct(m.currentDrawdownPct)} from high`);
        parts.push(`${fmtPct(m.annualizedVolPct)} vol`);
      } else if (lens === "quality") {
        parts.push(`${fmtPct(m.freeCashFlowMarginPct)} free cash flow margin`);
        parts.push(`${fmtPct(m.operatingMarginPct)} op margin`);
        parts.push(`${fmtPct(m.revenueGrowthYoyPct)} sales growth`);
      } else if (lens === "sponsor") {
        parts.push(`${fmtPct(m.institutionalSharesChangedQoqPct)} inst QoQ`);
        parts.push(`${fmtPct(m.institutionalOwnershipPct)} inst owned`);
        parts.push(`${confidenceLabel(m.coverageScore)} coverage`);
      } else {
        parts.push(`${fmtPct(m.returnPct)} since start`);
        parts.push(`${fmtPct(m.return20dPct)} 20D`);
        parts.push(`${fmtPct(m.maxDrawdownPct)} max drawdown`);
      }
      return parts.join(" | ");
    }

    function setupRunStrip() {
      const qa = DATA.qa || {};
      const best = baskets.slice().sort((a, b) => b.returnPct - a.returnPct)[0];
      const warnings = qa.summary?.warnings ?? (qa.warnings || []).length;
      const marketStatus = DATA.alpacaMarketStatus?.sourceProvider
        ? (DATA.alpacaMarketStatus.isOpen ? "Open" : "Closed")
        : null;
      document.getElementById("range-copy").textContent =
        `${DATA.methodology.startDate} -> ${DATA.methodology.endDate} | ${DATA.methodology.weighting} | ${DATA.methodology.priceField}`;
      const tiles = marketStatus ? [
        ["QA", qa.status || "n/a"],
        ["Market", marketStatus],
        ["Sectors", DATA.metrics.length],
        ["Tickers", DATA.tickers.length],
        ["Leader", best ? best.short : "n/a"]
      ] : [
        ["QA", qa.status || "n/a"],
        ["Sectors", DATA.metrics.length],
        ["Tickers", DATA.tickers.length],
        ["Leader", best ? best.short : "n/a"],
        ["Warnings", warnings]
      ];
      document.getElementById("run-strip").innerHTML = tiles.slice(0, 4).map(([label, value]) => `
        <div class="run-tile">
          <div class="tile-label">${label}</div>
          <div class="tile-value" title="${label === "Market" ? escapeHtml(`Alpaca clock: next open ${DATA.alpacaMarketStatus.nextOpen || "n/a"}`) : ""}">${value}</div>
        </div>
      `).join("");
    }

    function renderLensControls() {
      document.getElementById("lens-controls").innerHTML = lensDefs.map(l => `
        <button data-action="lens" data-lens="${l.id}" class="${state.lens === l.id ? "active" : ""}">${l.label}</button>
      `).join("");
    }

    async function apiJson(path, options = {}) {
      const response = await fetch(path, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) }
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
      return payload;
    }

    async function refreshWorkbenchState(quiet = false) {
      try {
        const payload = await apiJson("/api/state");
        state.setupAvailable = true;
        state.setupState = payload;
        state.runStatus = payload.run || state.runStatus;
        state.openaiStatus = payload.openai || state.openaiStatus;
        state.openaiModel = state.openaiStatus?.model || state.openaiModel;
        if (!state.setupCategory && payload.categories?.length) state.setupCategory = payload.categories[0].id;
        if (state.view === "setup") renderSetup();
        return payload;
      } catch (error) {
        state.setupAvailable = false;
        if (!quiet) state.setupMessage = "Start the workbench server to edit baskets and rerun the pipeline.";
        if (state.view === "setup") renderSetup();
        return null;
      }
    }

    async function refreshPortfolioReview(quiet = false) {
      try {
        const payload = await apiJson("/api/portfolio-review/current");
        state.portfolioReview = Object.keys(payload || {}).length ? payload : null;
        if (state.view === "portfolio-review") renderPortfolioReview();
        return payload;
      } catch (error) {
        if (!quiet) state.portfolioReviewMessage = "Start the workbench server to run portfolio review.";
        if (state.view === "portfolio-review") renderPortfolioReview();
        return null;
      }
    }

    async function runPortfolioReview() {
      state.portfolioReviewBusy = true;
      state.portfolioReviewMessage = "Running portfolio review...";
      renderPortfolioReview();
      try {
        const payload = await apiJson("/api/portfolio-review/run", {
          method: "POST",
          body: JSON.stringify({
            goalWeeklyReturnPct: Number(state.portfolioReviewGoal || 1),
            portfolioIds: ["app_metrics", "web_metrics"],
            refreshData: Boolean(state.portfolioReviewRefreshData)
          })
        });
        state.portfolioReview = payload;
        state.portfolioReviewMessage = `Review ${payload.run_id || ""} complete.`;
      } catch (error) {
        state.portfolioReviewMessage = error.message;
      } finally {
        state.portfolioReviewBusy = false;
        renderPortfolioReview();
      }
    }

    async function importPortfolioCsv() {
      if (!state.portfolioImportText.trim()) {
        state.portfolioImportMessage = "Choose a CSV file or paste CSV text first.";
        renderPortfolioReview();
        return;
      }
      try {
        const payload = await apiJson("/api/portfolio-review/import-csv", {
          method: "POST",
          body: JSON.stringify({
            portfolioId: state.portfolioImportId || "uploaded_portfolio",
            runDate: new Date().toISOString().slice(0, 10),
            capital: 100000,
            csvText: state.portfolioImportText
          })
        });
        state.portfolioImportMessage = `Imported ${payload.summary?.position_count || 0} position(s) into ${payload.portfolio_id}.`;
      } catch (error) {
        state.portfolioImportMessage = error.message;
      }
      renderPortfolioReview();
    }

    async function searchSetupCandidates() {
      if (!state.setupAvailable || !state.setupCategory) return;
      try {
        const payload = await apiJson(`/api/categories/${encodeURIComponent(state.setupCategory)}/search?q=${encodeURIComponent(state.setupSearch)}`);
        state.setupResults = payload.results || [];
        if (!state.pendingChanges) state.setupMessage = "";
        renderSetup();
      } catch (error) {
        state.setupMessage = error.message;
        renderSetup();
      }
    }

    async function mutateSetup(path, body) {
      try {
        state.setupState = await apiJson(path, { method: "POST", body: JSON.stringify(body || {}) });
        state.pendingChanges = true;
        state.setupMessage = "Changes saved. Run Full Analysis to apply them to the dashboard.";
        await searchSetupCandidates();
      } catch (error) {
        state.setupMessage = error.message;
        renderSetup();
      }
    }

    async function saveOpenAiSessionKey() {
      const keyInput = document.getElementById("openai-key");
      const modelInput = document.getElementById("openai-model");
      const apiKey = keyInput?.value || "";
      const model = modelInput?.value || state.openaiModel;
      if (!apiKey.trim()) {
        state.intakeMessage = "Paste an OpenAI key first. It is only held in server memory for this workbench session.";
        renderSetup();
        return;
      }
      try {
        state.openaiStatus = await apiJson("/api/openai/key", { method: "POST", body: JSON.stringify({ apiKey, model }) });
        state.openaiModel = state.openaiStatus.model || model;
        if (keyInput) keyInput.value = "";
        state.intakeMessage = "OpenAI key is active in this server session. It was not written to config or HTML.";
        renderSetup();
      } catch (error) {
        state.intakeMessage = error.message;
        renderSetup();
      }
    }

    async function forgetOpenAiSessionKey() {
      try {
        state.openaiStatus = await apiJson("/api/openai/key", { method: "POST", body: JSON.stringify({ forget: true, model: state.openaiModel }) });
        state.intakeMessage = "Session OpenAI key cleared. Env var fallback still works if OPENAI_API_KEY is exported.";
        renderSetup();
      } catch (error) {
        state.intakeMessage = error.message;
        renderSetup();
      }
    }

    async function parseTickerIntake() {
      state.intakeBusy = true;
      state.intakeMessage = "Parsing ticker text...";
      renderSetup();
      try {
        const payload = await apiJson("/api/ticker-intake/parse", { method: "POST", body: JSON.stringify({ text: state.intakeText }) });
        state.intakeRows = (payload.rows || []).map(row => ({
          ...row,
          recommendedBasket: row.localCandidateBasket || "",
          taxonomyPath: row.localTaxonomyPath || [],
          confidence: row.localCandidateBasket ? 0.7 : 0,
          rationale: row.localCandidateBasket ? `Local taxonomy candidate for ${row.localCandidateBasket}.` : "Parsed ticker; needs LLM classification.",
          suggestedNote: row.localNote || "",
          selected: false
        }));
        state.intakeMessage = state.intakeRows.length ? `Parsed ${state.intakeRows.length} ticker(s). Classify with OpenAI to assign taxonomy paths.` : "No ticker symbols found.";
      } catch (error) {
        state.intakeMessage = error.message;
      } finally {
        state.intakeBusy = false;
        renderSetup();
      }
    }

    async function fetchTickerContext(refresh = false) {
      state.intakeBusy = true;
      state.intakeMessage = refresh ? "Refreshing web context in parallel..." : "Fetching web context in parallel...";
      renderSetup();
      try {
        const payload = await apiJson("/api/ticker-intake/context", {
          method: "POST",
          body: JSON.stringify({ text: state.intakeText, refresh, workers: 8 })
        });
        state.intakeRows = (payload.rows || []).map(row => ({
          ...row,
          recommendedBasket: row.localCandidateBasket || "",
          taxonomyPath: row.localTaxonomyPath || [],
          confidence: row.localCandidateBasket ? 0.7 : 0,
          rationale: row.localCandidateBasket
            ? `Local taxonomy candidate for ${row.localCandidateBasket}.`
            : row.heuristicReason || (row.externalContextStatus === "ok" ? "Web context fetched; ready for LLM classification." : "No external context found yet."),
          suggestedNote: row.localNote || "",
          selected: false
        }));
        const ok = state.intakeRows.filter(row => row.externalContextStatus === "ok").length;
        state.intakeMessage = `Fetched web context for ${ok}/${state.intakeRows.length} ticker(s) using ${payload.contextWorkers || 8} parallel worker(s). Now classify with OpenAI.`;
      } catch (error) {
        state.intakeMessage = error.message;
      } finally {
        state.intakeBusy = false;
        renderSetup();
      }
    }

    async function classifyTickerIntake() {
      state.intakeBusy = true;
      state.intakeMessage = "Fetching web context, then classifying tickers with OpenAI in parallel chunks...";
      renderSetup();
      try {
        const payload = await apiJson("/api/ticker-intake/classify", {
          method: "POST",
          body: JSON.stringify({ text: state.intakeText, model: state.openaiModel, contextWorkers: 8, llmWorkers: 4, chunkSize: 5 })
        });
        state.intakeRows = (payload.rows || []).map(row => ({ ...row, selected: Boolean(row.selected) }));
        state.openaiModel = payload.model || state.openaiModel;
        const selected = state.intakeRows.filter(row => row.selected).length;
        const contextOk = state.intakeRows.filter(row => row.externalContextStatus === "ok").length;
        const errorText = payload.classificationErrors?.length ? ` ${payload.classificationErrors.length} chunk error(s); review unclassified rows.` : "";
        state.intakeMessage = `Classified ${state.intakeRows.length} ticker(s) with ${state.openaiModel}; web context found for ${contextOk}. ${selected} ready to add after review.${errorText}`;
      } catch (error) {
        state.intakeMessage = error.message;
      } finally {
        state.intakeBusy = false;
        renderSetup();
      }
    }

    async function addApprovedTickerIntake() {
      const rows = state.intakeRows
        .filter(row => row.selected)
        .map(row => ({
          selected: true,
          ticker: row.ticker,
          basket: row.recommendedBasket,
          companyName: row.companyName,
          name: row.companyName,
          note: row.suggestedNote,
          suggestedNote: row.suggestedNote,
          taxonomyPath: row.taxonomyPath || []
        }));
      if (!rows.length) {
        state.intakeMessage = "Select at least one classified ticker before adding.";
        renderSetup();
        return;
      }
      state.intakeBusy = true;
      state.intakeMessage = "Adding approved tickers to config...";
      renderSetup();
      try {
        const payload = await apiJson("/api/ticker-intake/add", { method: "POST", body: JSON.stringify({ rows }) });
        state.setupState = payload.state || state.setupState;
        const addedTickers = (payload.added || []).map(row => `${row.ticker} -> ${row.basket}`).join(", ");
        const skipped = (payload.skipped || []).length;
        state.pendingChanges = true;
        state.intakeRows = state.intakeRows.map(row => rows.some(added => added.ticker === row.ticker) ? { ...row, selected: false, alreadyInConfig: true } : row);
        state.intakeMessage = addedTickers ? `Added ${addedTickers}. ${skipped ? `${skipped} skipped. ` : ""}Run Full Analysis to rebuild the dashboard.` : `No new tickers added. ${skipped} skipped.`;
        await searchSetupCandidates();
      } catch (error) {
        state.intakeMessage = error.message;
        renderSetup();
      } finally {
        state.intakeBusy = false;
        renderSetup();
      }
    }

    async function startWorkbenchRun() {
      try {
        state.runStatus = await apiJson("/api/run", {
          method: "POST",
          body: JSON.stringify({
            refreshPrices: state.refreshPrices,
            refreshFundamentals: state.refreshFundamentals,
            refreshPositioning: state.refreshPositioning,
            refreshOwnership: state.refreshOwnership
          })
        });
        state.setupMessage = "Pipeline run started.";
        renderSetup();
        pollRunStatus();
      } catch (error) {
        state.setupMessage = error.message;
        renderSetup();
      }
    }

    async function pollRunStatus() {
      if (!state.setupAvailable) return;
      try {
        state.runStatus = await apiJson("/api/run/status");
        if (state.view === "setup") renderSetup();
        if (state.runStatus?.running) {
          setTimeout(pollRunStatus, 1600);
        } else if (state.runStatus?.state === "complete") {
          state.pendingChanges = false;
          state.setupMessage = "Run complete. Reloading updated workstation...";
          setTimeout(() => {
            const url = new URL(window.location.href);
            url.searchParams.set("run", state.runStatus.runId || Date.now().toString());
            window.location.replace(url.toString());
          }, 1200);
        }
      } catch (error) {
        state.setupMessage = error.message;
        if (state.view === "setup") renderSetup();
      }
    }

    function svgEl(tag, attrs = {}) {
      const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
      return node;
    }

    function clearChart(container) {
      const el = typeof container === "string" ? document.getElementById(container) : container;
      if (!el) return null;
      el.innerHTML = "";
      return el;
    }

    function lineChart(containerId, series, opts = {}) {
      const el = clearChart(containerId);
      if (!el) return;
      const width = Math.max(320, el.clientWidth || 720);
      const height = opts.height || el.clientHeight || 330;
      const margin = { top: 22, right: opts.rightMargin || 92, bottom: 34, left: 48 };
      const svg = svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
      el.appendChild(svg);
      const pointSeries = series.map(s => ({
        ...s,
        points: s.points
          .map((p, i) => ({ ...p, i, time: Date.parse(`${p.date}T00:00:00`) }))
          .filter(p => isNum(p.value) && Number.isFinite(p.time))
      }));
      const all = pointSeries.flatMap(s => s.points);
      if (!all.length) {
        svg.appendChild(svgEl("text", { x: width / 2, y: height / 2, class: "axis", "text-anchor": "middle" })).textContent = "No series data";
        return;
      }
      const minTime = Math.min(...all.map(p => p.time));
      const maxTime = Math.max(...all.map(p => p.time));
      const minY = Math.min(...all.map(p => p.value));
      const maxY = Math.max(...all.map(p => p.value));
      const pad = Math.max(2, (maxY - minY) * 0.08);
      const x = t => margin.left + ((t - minTime) / Math.max(1, maxTime - minTime)) * (width - margin.left - margin.right);
      const y = v => margin.top + (1 - ((v - (minY - pad)) / ((maxY + pad) - (minY - pad)))) * (height - margin.top - margin.bottom);
      for (let i = 0; i < 5; i++) {
        const gy = margin.top + i * ((height - margin.top - margin.bottom) / 4);
        svg.appendChild(svgEl("line", { x1: margin.left, x2: width - margin.right, y1: gy, y2: gy, class: "grid-line" }));
        const val = maxY + pad - i * ((maxY + pad - (minY - pad)) / 4);
        const text = svgEl("text", { x: 10, y: gy + 4, class: "axis" });
        text.textContent = val.toFixed(0);
        svg.appendChild(text);
      }
      for (let i = 0; i < 4; i++) {
        const tx = minTime + i * ((maxTime - minTime) / 3);
        const gx = x(tx);
        svg.appendChild(svgEl("line", { x1: gx, x2: gx, y1: margin.top, y2: height - margin.bottom, class: "grid-line" }));
        const date = new Date(tx);
        const text = svgEl("text", { x: gx, y: height - 10, class: "axis", "text-anchor": "middle" });
        text.textContent = `${date.getMonth() + 1}/${date.getDate()}`;
        svg.appendChild(text);
      }
      const placedLineLabels = [];
      pointSeries.forEach(s => {
        const pts = s.points;
        if (!pts.length) return;
        const d = pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.time)},${y(p.value)}`).join(" ");
        const pathStyle = [
          `stroke-width:${s.strokeWidth || (s.benchmark ? 2.1 : opts.compare ? 3.2 : 2.5)}`,
          s.dash ? `stroke-dasharray:${s.dash}` : "",
          s.benchmark ? "opacity:.68" : ""
        ].filter(Boolean).join(";");
        svg.appendChild(svgEl("path", { d, stroke: s.color, class: `line-path ${opts.compare ? "compare-path" : ""} ${s.benchmark ? "bench-path" : ""}`, style: pathStyle }));
        const last = pts[pts.length - 1];
        const lx = clamp(x(last.time) + 8, margin.left, width - 56);
        const baseLy = y(last.value) + 4;
        let ly = clamp(baseLy, margin.top + 8, height - margin.bottom - 4);
        for (const offset of [0, 13, -13, 26, -26, 39, -39, 52, -52, 65, -65]) {
          const candidate = clamp(baseLy + offset, margin.top + 8, height - margin.bottom - 4);
          if (!placedLineLabels.some(p => Math.abs(p.x - lx) < 68 && Math.abs(p.y - candidate) < 13)) {
            ly = candidate;
            break;
          }
        }
        placedLineLabels.push({ x: lx, y: ly });
        svg.appendChild(svgEl("circle", { cx: x(last.time), cy: y(last.value), r: s.benchmark ? 3.2 : opts.compare ? 4.2 : 3.5, fill: s.color, class: "point" }));
        const label = svgEl("text", { x: lx, y: ly, class: "label" });
        label.textContent = s.name;
        svg.appendChild(label);
      });
    }

    function scatterChart(containerId, items, xKey, yKey, opts = {}) {
      const el = clearChart(containerId);
      if (!el) return;
      const width = Math.max(320, el.clientWidth || 720);
      const height = opts.height || el.clientHeight || 330;
      const margin = { top: 24, right: 20, bottom: 42, left: 54 };
      const svg = svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
      el.appendChild(svg);
      const points = items.filter(d => isNum(d[xKey]) && isNum(d[yKey]));
      if (!points.length) return;
      const minX = Math.min(...points.map(d => d[xKey]));
      const maxX = Math.max(...points.map(d => d[xKey]));
      const minY = Math.min(...points.map(d => d[yKey]));
      const maxY = Math.max(...points.map(d => d[yKey]));
      const xPad = Math.max(1, (maxX - minX) * .1);
      const yPad = Math.max(1, (maxY - minY) * .1);
      const x = v => margin.left + ((v - minX + xPad) / (maxX - minX + xPad * 2)) * (width - margin.left - margin.right);
      const y = v => margin.top + (1 - ((v - minY + yPad) / (maxY - minY + yPad * 2))) * (height - margin.top - margin.bottom);
      for (let i = 0; i < 5; i++) {
        const gx = margin.left + i * ((width - margin.left - margin.right) / 4);
        const gy = margin.top + i * ((height - margin.top - margin.bottom) / 4);
        svg.appendChild(svgEl("line", { x1: gx, x2: gx, y1: margin.top, y2: height - margin.bottom, class: "grid-line" }));
        svg.appendChild(svgEl("line", { x1: margin.left, x2: width - margin.right, y1: gy, y2: gy, class: "grid-line" }));
      }
      const xLabel = svgEl("text", { x: width / 2, y: height - 11, class: "axis", "text-anchor": "middle" });
      xLabel.textContent = opts.xLabel || xKey;
      svg.appendChild(xLabel);
      const yLabel = svgEl("text", { x: 15, y: height / 2, class: "axis", transform: `rotate(-90 15 ${height / 2})`, "text-anchor": "middle" });
      yLabel.textContent = opts.yLabel || yKey;
      svg.appendChild(yLabel);
      const placedLabels = [];
      points.forEach(d => {
        const g = svgEl("g", { role: "button", tabindex: "0", "data-basket": d.basket });
        const size = clamp((d[opts.sizeKey || "coverageScore"] || 50) / 8, 5, 13);
        const cx = x(d[xKey]);
        const cy = y(d[yKey]);
        let lx = cx + size + 4;
        let ly = cy + 4;
        while (placedLabels.some(p => Math.abs(p.x - lx) < 58 && Math.abs(p.y - ly) < 14)) {
          ly += 13;
          if (ly > height - margin.bottom) ly = cy - 11;
        }
        placedLabels.push({ x: lx, y: ly });
        g.appendChild(svgEl("circle", { cx, cy, r: size, fill: d.color, class: "point", opacity: .86 }));
        const label = svgEl("text", { x: Math.min(lx, width - 58), y: ly, class: "label" });
        label.textContent = d.short;
        g.appendChild(label);
        g.addEventListener("click", () => { state.selectedSector = d.basket; state.view = "sector"; render(); });
        svg.appendChild(g);
      });
    }

    function mrrDistributionStats(rows) {
      const scores = rows.map(row => row.candidateScore).filter(isNum);
      if (!scores.length) return null;
      const sorted = scores.slice().sort((a, b) => a - b);
      return {
        n: scores.length,
        min: sorted[0],
        max: sorted[sorted.length - 1],
        median: quantile(scores, 0.5),
        p75: quantile(scores, 0.75),
        p90: quantile(scores, 0.9),
        mean: avg(scores),
        spread: sorted[sorted.length - 1] - sorted[0]
      };
    }

    function mrrDistributionChart(containerId, rows, opts = {}) {
      const el = clearChart(containerId);
      if (!el) return;
      const width = Math.max(340, el.clientWidth || 760);
      const height = opts.height || el.clientHeight || 285;
      const compact = !!opts.compact || width < 540 || height < 240;
      const margin = compact
        ? { top: 30, right: 22, bottom: 30, left: 26 }
        : { top: 24, right: 26, bottom: 42, left: 44 };
      const svg = svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
      el.appendChild(svg);
      const scores = rows.map(row => row.candidateScore).filter(isNum);
      if (!scores.length) {
        svg.appendChild(svgEl("text", { x: width / 2, y: height / 2, class: "axis", "text-anchor": "middle" })).textContent = "No MRR scores";
        return;
      }
      const binCount = Math.max(8, Math.min(16, Math.round(Math.sqrt(scores.length) * 1.2)));
      const binWidth = 100 / binCount;
      const bins = Array.from({ length: binCount }, (_, i) => ({ min: i * binWidth, max: (i + 1) * binWidth, count: 0, names: [] }));
      rows.forEach(row => {
        if (!isNum(row.candidateScore)) return;
        const idx = Math.min(binCount - 1, Math.max(0, Math.floor(row.candidateScore / binWidth)));
        bins[idx].count += 1;
        if (bins[idx].names.length < 5) bins[idx].names.push(row.ticker || row.short || row.label || "");
      });
      const maxCount = Math.max(...bins.map(bin => bin.count), 1);
      const x = value => margin.left + (clamp(value, 0, 100) / 100) * (width - margin.left - margin.right);
      const y = value => margin.top + (1 - value) * (height - margin.top - margin.bottom);
      const stats = mrrDistributionStats(rows);
      for (let i = 0; i <= 5; i += 1) {
        const score = i * 20;
        const gx = x(score);
        svg.appendChild(svgEl("line", { x1: gx, x2: gx, y1: margin.top, y2: height - margin.bottom, class: "grid-line" }));
        const label = svgEl("text", { x: gx, y: height - 13, class: "axis", "text-anchor": "middle" });
        label.textContent = score;
        svg.appendChild(label);
      }
      for (let i = 0; i <= 4; i += 1) {
        const gy = margin.top + i * ((height - margin.top - margin.bottom) / 4);
        svg.appendChild(svgEl("line", { x1: margin.left, x2: width - margin.right, y1: gy, y2: gy, class: "grid-line" }));
      }
      if (isNum(stats?.p90)) {
        const bandX = x(stats.p90);
        svg.appendChild(svgEl("rect", {
          x: bandX,
          y: margin.top,
          width: Math.max(0, x(100) - bandX),
          height: height - margin.top - margin.bottom,
          fill: "rgba(8,112,79,.07)"
        }));
        if (!compact) {
          const bandLabel = svgEl("text", { x: clamp(bandX + 8, margin.left, width - 96), y: margin.top + 14, class: "dist-band-label" });
          bandLabel.textContent = "top decile";
          svg.appendChild(bandLabel);
        }
      }
      const meanScore = avg(scores) ?? 0;
      const std = Math.sqrt(avg(scores.map(score => (score - meanScore) ** 2)) ?? 0);
      const bandwidth = clamp(1.06 * (std || 10) * Math.pow(scores.length, -0.2), 5, 18);
      const densityPoints = [];
      for (let score = 0; score <= 100; score += 2) {
        const density = scores.reduce((sum, sample) => {
          const z = (score - sample) / bandwidth;
          return sum + Math.exp(-0.5 * z * z);
        }, 0) / (scores.length * bandwidth * Math.sqrt(2 * Math.PI));
        densityPoints.push({ score, density });
      }
      const maxDensity = Math.max(...densityPoints.map(point => point.density), 1e-6);
      const curve = densityPoints.map((point, index) => `${index === 0 ? "M" : "L"}${x(point.score)},${y(point.density / maxDensity)}`).join(" ");
      const fill = `${curve} L${x(100)},${height - margin.bottom} L${x(0)},${height - margin.bottom} Z`;
      svg.appendChild(svgEl("path", { d: fill, class: "dist-fill" }));
      bins.forEach(bin => {
        const left = x(bin.min);
        const right = x(bin.max);
        const barH = (bin.count / maxCount) * (height - margin.top - margin.bottom);
        const mid = (bin.min + bin.max) / 2;
        const fillColor = isNum(stats?.p90) && mid >= stats.p90
          ? "var(--green)"
          : isNum(stats?.p75) && mid >= stats.p75
            ? "var(--teal)"
            : isNum(stats?.median) && mid >= stats.median
              ? "color-mix(in srgb, var(--green) 54%, #fff)"
              : "color-mix(in srgb, var(--line-strong) 76%, #fff)";
        const rect = svgEl("rect", {
          x: left + 2,
          y: height - margin.bottom - barH,
          width: Math.max(2, right - left - 4),
          height: Math.max(0, barH),
          rx: 5,
          class: "dist-bar",
          fill: fillColor
        });
        const title = svgEl("title");
        title.textContent = `${bin.min.toFixed(0)}-${bin.max.toFixed(0)} MRR: ${bin.count} tickers${bin.names.length ? ` | ${bin.names.filter(Boolean).join(", ")}` : ""}`;
        rect.appendChild(title);
        svg.appendChild(rect);
      });
      svg.appendChild(svgEl("path", { d: curve, class: "dist-curve" }));
      const markers = [
        { label: "median", value: stats?.median, color: "var(--ink)" },
        { label: "p75", value: stats?.p75, color: "var(--amber)" },
        { label: "p90", value: stats?.p90, color: "var(--violet)" },
        { label: "top", value: stats?.max, color: "var(--green)" }
      ].filter(marker => isNum(marker.value))
        .filter(marker => !compact || ["median", "p90", "top"].includes(marker.label));
      let markerLane = 0;
      let lastMarkerX = -999;
      markers.forEach(marker => {
        const mx = x(marker.value);
        svg.appendChild(svgEl("line", { x1: mx, x2: mx, y1: margin.top - 2, y2: height - margin.bottom, stroke: marker.color, class: "dist-marker" }));
        const nearRight = mx > width - (compact ? 70 : 82);
        if (Math.abs(mx - lastMarkerX) < 46) markerLane += 1;
        else markerLane = 0;
        lastMarkerX = mx;
        const label = svgEl("text", {
          x: nearRight ? clamp(mx - 5, margin.left + 48, width - margin.right) : clamp(mx + 5, margin.left, width - 62),
          y: margin.top + 12 + (markerLane % 3) * 13,
          class: "dist-marker-label",
          "text-anchor": nearRight ? "end" : "start"
        });
        label.textContent = `${marker.label} ${marker.value.toFixed(0)}`;
        svg.appendChild(label);
      });
      if (!compact) {
        const xLabel = svgEl("text", { x: width / 2, y: height - 2, class: "axis", "text-anchor": "middle" });
        xLabel.textContent = "MRR score";
        svg.appendChild(xLabel);
        const yLabel = svgEl("text", { x: 14, y: height / 2, class: "axis", transform: `rotate(-90 14 ${height / 2})`, "text-anchor": "middle" });
        yLabel.textContent = "Ticker count / KDE";
        svg.appendChild(yLabel);
      }
    }

    function heatColor(value, min, max, invert = false, mode = "green") {
      if (!isNum(value)) return "#eef0ea";
      const ratioRaw = max === min ? 0.5 : (value - min) / (max - min);
      const ratio = clamp(invert ? 1 - ratioRaw : ratioRaw, 0, 1);
      if (mode === "amber") return `color-mix(in srgb, #f7f8f3 ${Math.round((1 - ratio) * 72)}%, var(--amber))`;
      if (mode === "violet") return `color-mix(in srgb, #f7f8f3 ${Math.round((1 - ratio) * 72)}%, var(--violet))`;
      if (ratio < 0.48) return `color-mix(in srgb, #f7f8f3 ${Math.round(ratio * 85)}%, var(--red))`;
      return `color-mix(in srgb, #f7f8f3 ${Math.round((1 - ratio) * 70)}%, var(--green))`;
    }

    function heatmapReference(columns) {
      const defs = columns.filter(col => col.description);
      return `<div class="heatmap-reference">
        <div class="legend-row">
          <span class="legend-chip"><span class="legend-swatch" style="background:var(--green)"></span>Green: stronger rank</span>
          <span class="legend-chip"><span class="legend-swatch" style="background:var(--red)"></span>Red: weaker rank</span>
          <span class="legend-chip"><span class="legend-swatch" style="background:var(--violet)"></span>Purple: short/crowding exposure</span>
          <span class="legend-chip"><span class="legend-swatch" style="background:#eef0ea"></span>Gray: missing</span>
        </div>
        <div class="reference-grid">
          ${defs.map(col => `<div><strong>${escapeHtml(col.label)}:</strong> ${escapeHtml(col.description)}</div>`).join("")}
        </div>
      </div>`;
    }

    function candidateHeatmapColumns() {
      const selectedMetrics = activeCandidateMetrics();
      return [
        { key: "candidateScore", label: "MRR Score", description: "Mean reciprocal rank score across the active MRR inputs, normalized to 0-100.", format: v => isNum(v) ? v.toFixed(0) : "n/a" },
        { key: "candidateCoveragePct", label: "Rank Coverage", description: "Share of active MRR inputs available for this ticker; missing inputs contribute zero.", format: v => isNum(v) ? `${v.toFixed(0)}%` : "n/a" },
        ...selectedMetrics.map(metric => ({
          key: metric.key,
          label: metric.label,
          invert: metric.direction === "asc",
          mode: ["Positioning", "Options", "Speculation", "Cycle / Technicals"].includes(metric.group) ? "violet" : metric.group === "Risk" ? "amber" : "green",
          format: v => metric.group === "Cycle / Technicals" && isNum(v) ? v.toFixed(Math.abs(v) >= 10 ? 0 : 1) : fmtPct(v),
          description: `${metric.directionLabel}${metric.note ? `; ${metric.note}` : ""}`
        }))
      ];
    }

    function renderMrrInputPanel(rows) {
      const activeIds = state.candidateActiveMetricIds.length ? state.candidateActiveMetricIds : modeMetricIds(state.candidateMode);
      const draftIds = state.candidateDraftMetricIds.length ? state.candidateDraftMetricIds : [...activeIds];
      const activeSet = new Set(activeIds);
      const draftSet = new Set(draftIds);
      const groups = [...new Set(candidateMetricCatalog.map(metric => metric.group))];
      const mode = candidateModeDefs[state.candidateMode] || candidateModeDefs.balanced;
      const defaultIds = modeMetricIds(state.candidateMode);
      const customActive = !sameMetricIds(activeIds, defaultIds);
      const dirty = state.candidateInputsDirty;
      const metricRows = rows || [];
      state.candidateVisibleRowCount = metricRows.length;
      const activeReceipt = `${activeIds.length} active inputs`;
      const draftReceipt = dirty ? `${draftIds.length} draft selected` : `${draftIds.length} selected`;
      const activeTape = activeCandidateMetrics().map(metric => `<span>${escapeHtml(metric.label)}</span>`).join("");
      const statusClass = !draftIds.length ? "error" : state.candidateCalcStatus === "calculating" ? "calculating" : dirty ? "pending" : "current";
      const statusTitle = !draftIds.length
        ? "MRR cannot run"
        : state.candidateCalcStatus === "calculating"
          ? "Recalculating MRR"
          : dirty
            ? "MRR inputs changed, results not yet recalculated"
            : "MRR calculation current";
      const statusDetail = !draftIds.length
        ? "Select at least one input. The prior MRR result remains on screen until a valid recalculation is applied."
        : state.candidateCalcStatus === "calculating"
          ? `Ranking ${metricRows.length} rows in the browser. No pipeline or backend run is required.`
          : dirty
            ? `The table and heatmap still reflect ${activeIds.length} active inputs. Click Recalculate MRR to apply the ${draftIds.length}-input draft.`
            : `Version ${state.candidateCalcVersion} | last button calculation ${state.candidateLastCalcAt} | current view ${metricRows.length} rows | client-side calculation; backend/pipeline not invoked.`;
      return `<div class="mrr-input-panel">
        <div class="mrr-input-head">
          <div>
            <h3>MRR Inputs</h3>
            <p class="subtle">Select metrics, then recalculate. Missing selected inputs contribute zero to reciprocal-rank score.</p>
          </div>
          <div class="compare-strip">
            <button class="primary-btn" data-action="apply-mrr-inputs" ${!draftIds.length || state.candidateCalcStatus === "calculating" ? "disabled" : ""}>${state.candidateCalcStatus === "calculating" ? "Recalculating..." : "Recalculate MRR"}</button>
            <button class="small-btn" data-action="reset-mrr-inputs">Reset mode defaults</button>
          </div>
        </div>
        <div class="mrr-status ${statusClass}">
          <strong>${statusTitle}</strong>
          <span>${statusDetail}</span>
        </div>
        <div class="mrr-receipt">
          <span class="coverage-badge ${dirty ? "warn" : "good"}">${dirty ? "pending recalculation" : "current"}</span>
          <span>${activeReceipt}</span>
          <span>${draftReceipt}</span>
          <span>${customActive ? `customized from ${mode.label}` : `${mode.label} defaults`}</span>
          <span>ties use average rank</span>
          <span>missing selected inputs = zero contribution</span>
        </div>
        <div class="mrr-active-tape">${activeTape}</div>
        ${state.candidateInputMessage ? `<div class="warning">${escapeHtml(state.candidateInputMessage)}</div>` : ""}
        <div class="mrr-input-grid">
          ${groups.map(group => `
            <div class="mrr-input-group">
              <h3>${escapeHtml(group)}</h3>
              ${candidateMetricCatalog.filter(metric => metric.group === group).map(metric => {
                const draftSelected = draftSet.has(metric.id);
                const activeSelected = activeSet.has(metric.id);
                const available = metricRows.filter(row => isNum(metricValue(row, metric))).length;
                return `<button class="mrr-toggle ${draftSelected ? "active" : ""} ${draftSelected !== activeSelected ? "pending" : ""}" data-action="toggle-mrr-input" data-metric="${metric.id}">
                  <span class="metric-name">${escapeHtml(metric.label)}</span>
                  <span class="metric-dir">${metric.direction === "asc" ? "lower" : "higher"}</span>
                  <span class="metric-availability">${available}/${metricRows.length} rows | ${escapeHtml(metric.directionLabel)}${metric.note ? ` | ${escapeHtml(metric.note)}` : ""}</span>
                </button>`;
              }).join("")}
            </div>
          `).join("")}
        </div>
      </div>`;
    }

    function renderHeatmap(containerId, rows, columns) {
      const el = clearChart(containerId);
      if (!el) return;
      el.classList.add("heatmap-table");
      el.style.setProperty("--cols", columns.length);
      const stats = Object.fromEntries(columns.map(col => {
        const vals = rows.map(row => row[col.key]).filter(isNum);
        return [col.key, { min: vals.length ? Math.min(...vals) : 0, max: vals.length ? Math.max(...vals) : 1 }];
      }));
      el.innerHTML = `
        <div class="heatmap-row">
          <div class="heatmap-cell heatmap-label">${columns.length ? "Name" : ""}</div>
          ${columns.map(col => `<div class="heatmap-cell heatmap-label" title="${escapeHtml(col.description || col.label)}">${escapeHtml(col.label)}</div>`).join("")}
        </div>
        ${rows.map(row => `
          <div class="heatmap-row" data-action="${row.basket ? "sector" : "ticker"}" data-sector="${row.basket || ""}" data-ticker="${row.ticker || ""}">
            <div class="heatmap-cell heatmap-label"><span class="chip-dot" style="background:${row.color || (row.baskets || [])[0]?.color || "var(--line-strong)"}"></span>${row.short || row.ticker}</div>
            ${columns.map(col => {
              const s = stats[col.key];
              const bg = heatColor(row[col.key], s.min, s.max, col.invert, col.mode);
              const text = col.format ? col.format(row[col.key]) : fmtPct(row[col.key]);
              return `<div class="heatmap-cell" title="${escapeHtml(col.description || col.label)}" style="background:${bg}">${text}</div>`;
            }).join("")}
          </div>
        `).join("")}
      `;
    }

    function positioningMap(containerId, rows, opts = {}) {
      const el = clearChart(containerId);
      if (!el) return;
      const width = Math.max(320, el.clientWidth || 720);
      const height = opts.height || el.clientHeight || 330;
      const margin = { top: 26, right: 24, bottom: 44, left: 58 };
      const svg = svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
      el.appendChild(svg);
      const institutionalPoints = rows.filter(d => isNum(d.shortPctFloat) && isNum(d.institutionalSharesChangedQoqPct));
      const pressurePoints = rows.filter(d => isNum(d.shortPctFloat) && isNum(d.daysToCover));
      const sparseInstitutional = institutionalPoints.length < Math.ceil(rows.length * 0.5);
      const usePressureFallback = opts.allowPressureFallback && pressurePoints.length > institutionalPoints.length && sparseInstitutional;
      const points = usePressureFallback ? pressurePoints : institutionalPoints;
      if (!points.length) {
        svg.appendChild(svgEl("text", { x: width / 2, y: height / 2, class: "axis", "text-anchor": "middle" })).textContent = "No usable positioning pair";
        return;
      }
      const yKey = usePressureFallback ? "daysToCover" : "institutionalSharesChangedQoqPct";
      const yAxisLabel = usePressureFallback ? "Days to cover" : "Institutional shares QoQ";
      const minX = Math.min(0, ...points.map(d => d.shortPctFloat));
      const maxX = Math.max(12, ...points.map(d => d.shortPctFloat));
      const minY = usePressureFallback ? Math.min(0, ...points.map(d => d[yKey])) : Math.min(-10, ...points.map(d => d[yKey]));
      const maxY = usePressureFallback ? Math.max(5, ...points.map(d => d[yKey])) : Math.max(10, ...points.map(d => d[yKey]));
      const x = v => margin.left + ((v - minX) / Math.max(1, maxX - minX)) * (width - margin.left - margin.right);
      const y = v => margin.top + (1 - ((v - minY) / Math.max(1, maxY - minY))) * (height - margin.top - margin.bottom);
      for (let i = 0; i < 5; i++) {
        const gx = margin.left + i * ((width - margin.left - margin.right) / 4);
        const gy = margin.top + i * ((height - margin.top - margin.bottom) / 4);
        svg.appendChild(svgEl("line", { x1: gx, x2: gx, y1: margin.top, y2: height - margin.bottom, class: "grid-line" }));
        svg.appendChild(svgEl("line", { x1: margin.left, x2: width - margin.right, y1: gy, y2: gy, class: "grid-line" }));
      }
      if (minX <= 10 && maxX >= 10) svg.appendChild(svgEl("line", { x1: x(10), x2: x(10), y1: margin.top, y2: height - margin.bottom, stroke: "rgba(167,102,20,.55)", "stroke-dasharray": "4 4" }));
      if (!usePressureFallback && minY <= 0 && maxY >= 0) svg.appendChild(svgEl("line", { x1: margin.left, x2: width - margin.right, y1: y(0), y2: y(0), stroke: "rgba(25,27,24,.28)", "stroke-dasharray": "4 4" }));
      if (usePressureFallback && minY <= 5 && maxY >= 5) svg.appendChild(svgEl("line", { x1: margin.left, x2: width - margin.right, y1: y(5), y2: y(5), stroke: "rgba(167,102,20,.45)", "stroke-dasharray": "4 4" }));
      const xLabel = svgEl("text", { x: width / 2, y: height - 12, class: "axis", "text-anchor": "middle" });
      xLabel.textContent = "Short interest % float";
      svg.appendChild(xLabel);
      const yLabel = svgEl("text", { x: 16, y: height / 2, class: "axis", transform: `rotate(-90 16 ${height / 2})`, "text-anchor": "middle" });
      yLabel.textContent = yAxisLabel;
      svg.appendChild(yLabel);
      if (usePressureFallback || points.length < rows.length) {
        const note = svgEl("text", { x: margin.left, y: margin.top - 8, class: "axis" });
        note.textContent = usePressureFallback
          ? "Institutional QoQ sparse; showing short-pressure fallback"
          : `${points.length}/${rows.length} plotted; missing short or institutional fields`;
        svg.appendChild(note);
      }
      const placed = [];
      points.forEach(d => {
        const cx = x(d.shortPctFloat);
        const cy = y(d[yKey]);
        const sizeBase = usePressureFallback ? (d.shortVolumeRatioPct || d.coverageScore || 40) : (d.institutionalOwnershipPct || d.coverageScore || 40);
        const size = clamp(sizeBase / 8, 5, 14);
        const g = svgEl("g", { role: "button", tabindex: "0", "data-basket": d.basket || "", "data-ticker": d.ticker || "" });
        g.appendChild(svgEl("circle", { cx, cy, r: size, fill: d.color || (d.baskets || [])[0]?.color || "var(--green)", class: "point", opacity: .88 }));
        let lx = cx + size + 4;
        let ly = cy + 4;
        while (placed.some(p => Math.abs(p.x - lx) < 58 && Math.abs(p.y - ly) < 14)) ly += 12;
        placed.push({ x: lx, y: ly });
        const label = svgEl("text", { x: clamp(lx, margin.left, width - 64), y: clamp(ly, margin.top + 8, height - margin.bottom), class: "label" });
        label.textContent = d.short || d.ticker;
        g.appendChild(label);
        g.addEventListener("click", () => {
          if (d.basket) { state.selectedSector = d.basket; state.view = "sector"; render(); }
          if (d.ticker) openTicker(d.ticker);
        });
        svg.appendChild(g);
      });
    }

    function bars(containerId, items, key, opts = {}) {
      const el = clearChart(containerId);
      if (!el) return;
      const width = Math.max(320, el.clientWidth || 720);
      const height = opts.height || el.clientHeight || 300;
      const margin = { top: 16, right: 76, bottom: 22, left: 92 };
      const svg = svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
      el.appendChild(svg);
      const xs = items.filter(d => isNum(d[key]));
      if (!xs.length) return;
      const maxAbs = Math.max(...xs.map(d => Math.abs(d[key])), 1);
      const rowH = (height - margin.top - margin.bottom) / xs.length;
      const zero = margin.left + (width - margin.left - margin.right) / 2;
      xs.forEach((d, i) => {
        const y = margin.top + i * rowH + rowH * .18;
        const val = d[key];
        const w = (Math.abs(val) / maxAbs) * ((width - margin.left - margin.right) / 2);
        const x = val >= 0 ? zero : zero - w;
        svg.appendChild(svgEl("text", { x: 10, y: y + rowH * .45, class: "axis" })).textContent = d.ticker || d.short || d.label;
        svg.appendChild(svgEl("rect", { x, y, width: Math.max(1, w), height: Math.max(8, rowH * .55), rx: 4, fill: val >= 0 ? (d.color || "var(--green)") : "var(--red)" }));
        const label = svgEl("text", { x: val >= 0 ? x + w + 6 : x - 6, y: y + rowH * .45, class: "axis", "text-anchor": val >= 0 ? "start" : "end" });
        label.textContent = opts.format ? opts.format(val) : fmtPct(val);
        svg.appendChild(label);
      });
      svg.appendChild(svgEl("line", { x1: zero, x2: zero, y1: margin.top, y2: height - margin.bottom, class: "grid-line" }));
    }

    function breadthChart(containerId, basketId) {
      const rows = DATA.breadth?.[basketId] || [];
      const series = [
        { name: "Positive", color: "var(--green)", points: rows.map(r => ({ date: r.date, value: r.positiveSinceStartPct })) },
        { name: "Above 10DMA", color: "var(--teal)", points: rows.map(r => ({ date: r.date, value: r.above10dmaPct })) }
      ];
      lineChart(containerId, series, { height: 230 });
    }

    function rankCard(m, scoreKey = currentLens().score, lens = currentLens().id) {
      const score = m[scoreKey] ?? 0;
      return `
        <button class="rank-card" data-action="sector" data-sector="${m.basket}">
          <div class="rank-top">
            <div class="rank-name">
              <span class="swatch" style="background:${m.color}"></span>
              <div>
                <div class="rank-title">${m.label}</div>
                <div class="subtle">${m.stance} | ${confidenceLabel(m.coverageScore)} confidence</div>
              </div>
            </div>
            <span class="${colorForScore(score)}">${score.toFixed(0)}</span>
          </div>
          <div class="why">${whyFor(m, lens)}</div>
        </button>
      `;
    }

    function selectedSeries() {
      const series = [...state.selectedBaskets].map(id => {
        const m = basketById.get(id);
        return {
          name: m.short,
          color: m.displayColor || m.color,
          dash: m.compareDash || "",
          strokeWidth: m.compareStrokeWidth || 3.2,
          points: (DATA.daily[id] || []).map(p => ({ date: p.date, value: p.index }))
        };
      });
      benchmarks.forEach(b => {
        if (!state.showBenchmarks.has(b.id)) return;
        const bench = DATA.benchmarks?.[b.id];
        if (!bench) return;
        series.push({ name: b.label, color: b.color, dash: "4 4", strokeWidth: 2.1, benchmark: true, points: bench.series.map(p => ({ date: p.date, value: p.value })) });
      });
      return series;
    }

    function renderOverview() {
      const lens = currentLens();
      const ranked = topBy(lens.score, 6);
      const bestReturn = baskets.slice().sort((a, b) => b.returnPct - a.returnPct)[0];
      const bestRisk = baskets.slice().sort((a, b) => b.riskControlScore - a.riskControlScore)[0];
      const bestTorque = baskets.slice().sort((a, b) => b.torqueScore - a.torqueScore)[0];
      const overviewColumns = [
        { key: "returnPct", label: "Return", description: "Equal-weight basket return since the analysis start date." },
        { key: "return20dPct", label: "20D Return", description: "Basket return over the latest 20 trading-day window." },
        { key: "currentDrawdownPct", label: "Drawdown", description: "Distance from the basket's high during the analysis window." },
        { key: "annualizedVolPct", label: "Volatility", mode: "amber", description: "Annualized realized volatility; amber means more movement, not automatically better." },
        { key: "shortPctFloat", label: "Short Interest % Float", mode: "violet", description: "Reported short interest as a percentage of public float." },
        { key: "institutionalSharesChangedQoqPct", label: "Institutional Shares Change", description: "Quarter-over-quarter change in institutional shares where 13F data is available." },
        { key: "freeCashFlowMarginPct", label: "Free Cash Flow Margin", description: "Latest free cash flow margin from fundamentals data." },
        { key: "coverageScore", label: "Data Coverage", description: "Average coverage across fundamentals, options, short interest, and institutional data.", format: v => isNum(v) ? v.toFixed(0) : "n/a" }
      ];
      document.getElementById("view-root").innerHTML = `
        <section class="grid overview-grid">
          <div class="panel">
            <div class="panel-head">
              <div><h2>Decision Queue</h2><p class="subtle">${lens.label} screen</p></div>
            </div>
            <div class="panel-body">${ranked.map(m => rankCard(m, lens.score, lens.id)).join("")}</div>
          </div>

          <div class="panel">
            <div class="panel-head">
              <div><h2>Market Map</h2><p class="subtle">Total return versus risk discipline</p></div>
              <button class="small-btn" data-action="view" data-view="compare">Compare</button>
            </div>
            <div class="panel-body">
              <div class="stat-grid" style="margin-bottom:12px">
                <div class="stat"><div class="tile-label">Leadership</div><div class="value ${cls(bestReturn.returnPct)}">${bestReturn.short}</div><p class="subtle">${fmtPct(bestReturn.returnPct)}</p></div>
                <div class="stat"><div class="tile-label">Risk control</div><div class="value">${bestRisk.short}</div><p class="subtle">${bestRisk.riskControlScore.toFixed(0)} score</p></div>
                <div class="stat"><div class="tile-label">Volatility setup</div><div class="value">${bestTorque.short}</div><p class="subtle">${bestTorque.torqueScore.toFixed(0)} torque</p></div>
                <div class="stat"><div class="tile-label">QA warnings</div><div class="value">${DATA.qa?.summary?.warnings ?? (DATA.qa?.warnings || []).length ?? 0}</div><p class="subtle">${DATA.qa?.status || "n/a"}</p></div>
              </div>
              <div class="chart tall" id="overview-scatter"></div>
            </div>
          </div>

          <div class="panel">
            <div class="panel-head">
              <div><h2>Setup Radar</h2><p class="subtle">Best sector by analyst intent</p></div>
            </div>
            <div class="panel-body">
              ${lensDefs.filter(l => l.id !== "balanced").map(l => {
                const m = topBy(l.score, 1)[0];
                return `<div class="metric-row">
                  <div><strong>${l.label}</strong><div class="why">${whyFor(m, l.id)}</div></div>
                  <button class="score-pill" data-action="sector" data-sector="${m.basket}">${m.short}</button>
                </div>`;
              }).join("")}
            </div>
          </div>
        </section>
        <section class="grid two-col" style="margin-top:12px">
          <div class="panel">
            <div class="panel-head"><div><h2>Sector Setup Heatmap</h2><p class="subtle">Fast read across performance, risk, positioning, fundamentals, and confidence</p></div></div>
            <div class="panel-body"><div id="overview-heatmap"></div>${heatmapReference(overviewColumns)}</div>
          </div>
          <div class="panel">
            <div class="panel-head"><div><h2>Short Interest vs Institutional Bid</h2><p class="subtle">High short plus rising sponsorship is the squeeze/watch-turn zone</p></div></div>
            <div class="panel-body"><div class="chart" id="overview-positioning"></div></div>
          </div>
        </section>
      `;
      scatterChart("overview-scatter", baskets, "returnPct", "riskControlScore", {
        xLabel: "Total return since start",
        yLabel: "Risk control score",
        sizeKey: "coverageScore",
        height: 420
      });
      renderHeatmap("overview-heatmap", baskets.slice().sort((a, b) => b.balancedScore - a.balancedScore), overviewColumns);
      positioningMap("overview-positioning", baskets, { height: 330 });
    }

    function renderCompare() {
      const selected = baskets.filter(m => state.selectedBaskets.has(m.basket));
      const visibleBenchmarks = benchmarks.filter(b => state.showBenchmarks.has(b.id) && DATA.benchmarks?.[b.id]);
      const sorted = selected.slice().sort((a, b) => {
        const av = a[state.compareSort], bv = b[state.compareSort];
        const dir = state.compareDir === "asc" ? 1 : -1;
        return ((av ?? -9999) - (bv ?? -9999)) * dir;
      });
      const seriesKey = item => `<div class="series-key">
        ${seriesPreview(item.color, item.dash)}
        <div class="series-label"><strong>${escapeHtml(item.label)}</strong><span class="meta">${escapeHtml(item.meta)}</span></div>
        <span class="meta">${escapeHtml(dashName(item.dash))}</span>
      </div>`;
      document.getElementById("view-root").innerHTML = `
        <section class="compare-layout">
          <div class="panel">
            <div class="panel-head">
              <div><h2>Compare Workspace</h2><p class="subtle">${selected.length} selected baskets | ${visibleBenchmarks.length} benchmarks | ${DATA.methodology.endDate}</p></div>
            </div>
            <div class="panel-body">
              <div class="compare-toolbar">
                <div class="compare-selector">
                  ${baskets.map(m => `<button class="chip ${state.selectedBaskets.has(m.basket) ? "active" : ""}" data-action="toggle-basket" data-sector="${m.basket}"><span class="chip-dot" style="background:${m.displayColor || m.color}"></span>${m.short}</button>`).join("")}
                </div>
                <div class="compare-strip">
                  ${benchmarks.map(b => `<button class="chip ${state.showBenchmarks.has(b.id) ? "active" : ""}" data-action="bench" data-bench="${b.id}"><span class="chip-dot" style="background:${b.color}"></span>${b.label}</button>`).join("")}
                </div>
              </div>
              <div class="compare-legend">
                ${selected.map(m => seriesKey({ color: m.displayColor || m.color, dash: m.compareDash || "", label: m.short, meta: fmtPct(m.returnPct) })).join("")}
                ${visibleBenchmarks.map(b => seriesKey({ color: b.color, dash: "4 4", label: b.label, meta: "benchmark" })).join("")}
              </div>
              <div class="chart tall compare-chart" id="compare-line"></div>
            </div>
          </div>
          <div class="panel">
            <div class="panel-head"><div><h2>Selected Read</h2><p class="subtle">Sort by the metric that matters now</p></div></div>
            <div class="panel-body">
              <div class="table-wrap compare-table">
                <table>
                  <thead><tr>
                    ${[
                      ["label","Sector"],["balancedScore","Score"],["returnPct","Return"],["return20dPct","20D Return"],["currentDrawdownPct","Drawdown"],["annualizedVolPct","Volatility"],["shortPctFloat","Short Interest % Float"],["institutionalSharesChangedQoqPct","Institutional Shares Change"],["qualityScore","Quality"],["coverageScore","Confidence"]
                    ].map(([key,label]) => `<th data-action="sort-compare" data-key="${key}">${label}</th>`).join("")}
                  </tr></thead>
                  <tbody>
                    ${sorted.map(m => `<tr data-action="sector" data-sector="${m.basket}">
                      <td><div class="ticker-cell">${seriesPreview(m.displayColor || m.color, m.compareDash || "")}<strong>${m.label}</strong></div></td>
                      <td class="mono">${m.balancedScore.toFixed(0)}</td>
                      <td class="mono ${cls(m.returnPct)}">${fmtPct(m.returnPct)}</td>
                      <td class="mono ${cls(m.return20dPct)}">${fmtPct(m.return20dPct)}</td>
                      <td class="mono ${cls(m.currentDrawdownPct)}">${fmtPct(m.currentDrawdownPct)}</td>
                      <td class="mono">${fmtPct(m.annualizedVolPct)}</td>
                      <td class="mono">${fmtPct(m.shortPctFloat)}</td>
                      <td class="mono ${cls(m.institutionalSharesChangedQoqPct)}">${fmtPct(m.institutionalSharesChangedQoqPct)}</td>
                      <td class="mono">${m.qualityScore.toFixed(0)}</td>
                      <td class="mono">${confidenceLabel(m.coverageScore)}</td>
                    </tr>`).join("")}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      `;
      lineChart("compare-line", selectedSeries(), { height: 440, rightMargin: 112, compare: true });
    }

    function renderSectorList() {
      return `<div class="sector-list">
        ${baskets.slice().sort((a, b) => b.returnPct - a.returnPct).map(m => `
          <button class="sector-btn ${state.selectedSector === m.basket ? "active" : ""}" data-action="select-sector" data-sector="${m.basket}">
            <span class="chip-dot" style="background:${m.color}"></span>
            <span class="name">${m.short}</span>
            <span class="${cls(m.returnPct)} mono">${fmtPct(m.returnPct)}</span>
          </button>
        `).join("")}
      </div>`;
    }

    function renderSector() {
      const m = basketById.get(state.selectedSector) || baskets[0];
      const rawItems = (DATA.constituents[m.basket] || []).map(t => ({ ...(tickerBySymbol.get(t.ticker) || {}), ...t }));
      const items = rankCandidateRows(rawItems, state.candidateMode);
      const rankMode = candidateModeDefs[state.candidateMode] || candidateModeDefs.balanced;
      const candidateRows = items.slice().sort((a, b) => a.candidateRank - b.candidateRank);
      const topCandidate = candidateRows[0];
      const medianCoverage = avg(candidateRows.map(t => t.candidateCoveragePct)) ?? 0;
      const activeInputCount = activeCandidateMetrics().length;
      const sectorHeatmapColumns = candidateHeatmapColumns();
      const filtered = items.filter(t => {
        if (state.sectorFilter === "leaders") return t.returnPct >= 0;
        if (state.sectorFilter === "drawdown") return (t.currentDrawdownPct || 0) <= -8;
        if (state.sectorFilter === "squeeze") return (t.shortPctFloat || 0) >= 10 || (t.shortVolumeRatioPct || 0) >= 50;
        if (state.sectorFilter === "quality") return (t.freeCashFlowMarginPct || -999) >= 15 && (t.operatingMarginPct || -999) >= 10;
        return true;
      }).sort((a, b) => {
        const dir = state.sectorDir === "asc" ? 1 : -1;
        return ((a[state.sectorSort] ?? -9999) - (b[state.sectorSort] ?? -9999)) * dir;
      });
      const institutionalPairCount = items.filter(t => isNum(t.shortPctFloat) && isNum(t.institutionalSharesChangedQoqPct)).length;
      const shortPressurePairCount = items.filter(t => isNum(t.shortPctFloat) && isNum(t.daysToCover)).length;
      const useShortPressurePanel = shortPressurePairCount > institutionalPairCount && institutionalPairCount < Math.ceil(items.length * 0.5);
      const positioningTitle = !useShortPressurePanel && institutionalPairCount ? "Short Interest vs Institutional Bid" : shortPressurePairCount ? "Short Interest Pressure" : "Positioning Map";
      const positioningSubtitle = !useShortPressurePanel && institutionalPairCount
        ? "Ticker-level squeeze and sponsorship map"
        : shortPressurePairCount
          ? "Institutional coverage is sparse here, so this plots short float versus days to cover"
          : "No usable ticker-level positioning pair is available";
      document.getElementById("view-root").innerHTML = `
        <section class="sector-layout">
          ${renderSectorList()}
          <div class="grid">
            <div class="panel">
              <div class="panel-head">
                <div>
                  <h2>${m.label}</h2>
                  <p class="subtle">${m.stance} | ${confidenceLabel(m.coverageScore)} confidence | ${whyFor(m)}</p>
                </div>
                <button class="small-btn" data-action="add-compare" data-sector="${m.basket}">Add to compare</button>
              </div>
              <div class="panel-body">
                <div class="stat-grid">
                  <div class="stat"><div class="tile-label">Return</div><div class="value ${cls(m.returnPct)}">${fmtPct(m.returnPct)}</div><p class="subtle">20D ${fmtPct(m.return20dPct)}</p></div>
                  <div class="stat"><div class="tile-label">Drawdown</div><div class="value ${cls(m.currentDrawdownPct)}">${fmtPct(m.currentDrawdownPct)}</div><p class="subtle">Max ${fmtPct(m.maxDrawdownPct)}</p></div>
                  <div class="stat"><div class="tile-label">Positioning</div><div class="value">${m.squeezeScore.toFixed(0)}</div><p class="subtle">${fmtPct(m.shortPctFloat)} short float</p></div>
                  <div class="stat"><div class="tile-label">Fundamentals</div><div class="value">${m.qualityScore.toFixed(0)}</div><p class="subtle">${fmtPct(m.freeCashFlowMarginPct)} free cash flow margin</p></div>
                </div>
              </div>
            </div>

            <div class="grid two-col">
              <div class="panel">
                <div class="panel-head"><div><h2>Constituent Tape</h2><p class="subtle">Normalized from basket start</p></div></div>
                <div class="panel-body"><div class="chart" id="sector-lines"></div></div>
              </div>
              <div class="panel">
                <div class="panel-head"><div><h2>Breadth</h2><p class="subtle">Positive since start and above 10DMA</p></div></div>
                <div class="panel-body"><div class="chart short" id="sector-breadth"></div></div>
              </div>
            </div>

            <div class="grid two-col">
              <div class="panel">
                <div class="panel-head"><div><h2>Contribution</h2><p class="subtle">Equal-weight contribution estimate</p></div></div>
                <div class="panel-body"><div class="chart short" id="sector-attribution"></div></div>
              </div>
              <div class="panel">
                <div class="panel-head"><div><h2>Leaders / Laggards</h2><p class="subtle">Best and weakest constituents</p></div></div>
                <div class="panel-body">
                  <div class="split-list">
                    <div>${items.slice().sort((a,b)=>b.returnPct-a.returnPct).slice(0,4).map(t => `<div class="list-row"><button class="small-btn" data-action="ticker" data-ticker="${t.ticker}">${t.ticker}</button><span class="${cls(t.returnPct)}">${fmtPct(t.returnPct)}</span></div>`).join("")}</div>
                    <div>${items.slice().sort((a,b)=>a.returnPct-b.returnPct).slice(0,4).map(t => `<div class="list-row"><button class="small-btn" data-action="ticker" data-ticker="${t.ticker}">${t.ticker}</button><span class="${cls(t.returnPct)}">${fmtPct(t.returnPct)}</span></div>`).join("")}</div>
                  </div>
                </div>
              </div>
            </div>

            <div class="panel">
              <div class="panel-head">
                <div>
                  <h2>Candidate Ranker</h2>
                  <p class="subtle">${rankMode.description}</p>
                </div>
                ${candidateModeButtons()}
              </div>
              <div class="panel-body">
        <div class="rank-summary ${state.candidateCalcStatus === "current" && state.candidateInputMessage ? "mrr-flash" : ""}">
                  <div class="stat"><div class="tile-label">Top candidate</div><div class="value">${topCandidate?.ticker || "n/a"}</div><p class="subtle">${topCandidate ? `#${topCandidate.candidateRank} | MRR ${topCandidate.candidateScore.toFixed(0)}` : "No rankable rows"}</p></div>
                  <div class="stat"><div class="tile-label">Rank mode</div><div class="value">${rankMode.label}</div><p class="subtle">${activeInputCount} active inputs</p></div>
                  <div class="stat"><div class="tile-label">Median rank coverage</div><div class="value">${medianCoverage.toFixed(0)}%</div><p class="subtle">Missing inputs are penalized</p></div>
                  <div class="stat"><div class="tile-label">Best signal</div><div class="value">${topCandidate ? topCandidate.candidateScore.toFixed(0) : "n/a"}</div><p class="subtle">${topCandidate?.candidateWhy || "n/a"}</p></div>
                </div>
                ${renderMrrInputPanel(rawItems)}
                ${tickerTable(candidateRows, "sector", { compact: true })}
              </div>
            </div>

            <div class="grid two-col">
              <div class="panel">
                <div class="panel-head"><div><h2>Ticker Setup Heatmap</h2><p class="subtle">Ranker output plus the source metrics driving it</p></div></div>
                <div class="panel-body"><div id="sector-heatmap"></div>${heatmapReference(sectorHeatmapColumns)}</div>
              </div>
              <div class="panel">
                <div class="panel-head"><div><h2>${positioningTitle}</h2><p class="subtle">${positioningSubtitle}</p></div></div>
                <div class="panel-body"><div class="chart short" id="sector-positioning"></div></div>
              </div>
            </div>

            <div class="panel">
              <div class="panel-head">
                <div><h2>Constituent Drilldown</h2><p class="subtle">${filtered.length} of ${items.length} tickers</p></div>
                <div class="seg">
                  ${[
                    ["all","All"],["leaders","Leaders"],["drawdown","Pullbacks"],["squeeze","Squeeze"],["quality","Quality"]
                  ].map(([id,label]) => `<button class="${state.sectorFilter === id ? "active" : ""}" data-action="sector-filter" data-filter="${id}">${label}</button>`).join("")}
                </div>
              </div>
              <div class="panel-body">${tickerTable(filtered, "sector")}</div>
            </div>
          </div>
        </section>
      `;
      lineChart("sector-lines", items.map(t => ({ name: t.ticker, color: m.color, points: (t.series || []).map(p => ({ date: p.date, value: p.value })) })), { height: 330 });
      breadthChart("sector-breadth", m.basket);
      bars("sector-attribution", (DATA.attribution[m.basket] || []).slice(0, 8), "contributionPct", { height: 230, format: fmtPct });
      renderHeatmap("sector-heatmap", candidateRows, sectorHeatmapColumns);
      positioningMap("sector-positioning", items, { height: 230, allowPressureFallback: true });
    }

    function tickerTable(rows, scope, opts = {}) {
      const headers = [
        ["ticker","Ticker"],
        ["candidateRank","Setup Rank"],
        ["candidateScore","MRR Score"],
        ["candidateCoveragePct","Rank Coverage"],
        ["technicalExtremeScore","Cycle Score"],
        ["rsi14Percentile","RSI Percentile"],
        ["returnPct","Return"],
        ["return20dPct","20D Return"],
        ["currentDrawdownPct","Drawdown"],
        ["reboundFromLowPct","Rebound"],
        ["annualizedVolPct","Volatility"],
        ["shortPctFloat","Short Interest % Float"],
        ["institutionalSharesChangedQoqPct","Institutional Shares Change"],
        ["freeCashFlowMarginPct","Free Cash Flow Margin"],
        ["momentumScore","Momentum"],
        ["squeezeScore","Squeeze"],
        ["qualityScore","Quality"]
      ];
      const action = scope === "sector" ? "sort-sector" : "sort-ticker";
      return `<div class="table-wrap">
        <table>
          <thead><tr>${headers.map(([key,label]) => `<th data-action="${action}" data-key="${key}">${label}</th>`).join("")}</tr></thead>
          <tbody>
            ${rows.map(t => `<tr data-action="ticker" data-ticker="${t.ticker}">
              <td><div class="ticker-cell"><strong>${t.ticker}</strong><span class="subtle">${(t.baskets || [])[0]?.short || ""}</span></div>${t.candidateWhy ? `<div class="why">${escapeHtml(t.candidateWhy)}</div>` : ""}</td>
              <td class="mono">${isNum(t.candidateRank) ? `#${t.candidateRank}` : "n/a"}</td>
              <td class="mono">${isNum(t.candidateScore) ? t.candidateScore.toFixed(0) : "n/a"}</td>
              <td class="mono">${coverageBadge(t.candidateCoveragePct)}</td>
              <td class="mono">${isNum(t.technicalExtremeScore) ? t.technicalExtremeScore.toFixed(0) : "n/a"}${t.cyclicalState ? `<div>${cycleBadge(t.cyclicalState)}</div>` : ""}</td>
              <td class="mono">${fmtPctile(t.rsi14Percentile)}</td>
              <td class="mono ${cls(t.returnPct)}">${fmtPct(t.returnPct)}</td>
              <td class="mono ${cls(t.return20dPct)}">${fmtPct(t.return20dPct)}</td>
              <td class="mono ${cls(t.currentDrawdownPct)}">${fmtPct(t.currentDrawdownPct)}</td>
              <td class="mono ${cls(t.reboundFromLowPct)}">${fmtPct(t.reboundFromLowPct)}</td>
              <td class="mono">${fmtPct(t.annualizedVolPct)}</td>
              <td class="mono">${fmtPct(t.shortPctFloat)}</td>
              <td class="mono ${cls(t.institutionalSharesChangedQoqPct)}">${fmtPct(t.institutionalSharesChangedQoqPct)}</td>
              <td class="mono ${cls(t.freeCashFlowMarginPct)}">${fmtPct(t.freeCashFlowMarginPct)}</td>
              <td class="mono">${(t.momentumScore ?? 0).toFixed(0)}</td>
              <td class="mono">${(t.squeezeScore ?? 0).toFixed(0)}</td>
              <td class="mono">${(t.qualityScore ?? 0).toFixed(0)}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    }

    function renderTickers() {
      const scoreKey = state.tickerLens === "quality" ? "qualityScore" : state.tickerLens === "squeeze" ? "squeezeScore" : state.tickerLens === "rebound" ? "reboundScore" : "momentumScore";
      let rows = tickers.filter(t => {
        const hay = `${t.ticker} ${t.name}`.toLowerCase();
        if (state.tickerSearch && !hay.includes(state.tickerSearch.toLowerCase())) return false;
        if (state.tickerSector !== "all" && !(t.baskets || []).some(b => b.basket === state.tickerSector)) return false;
        if (state.tickerFilter === "positive" && t.returnPct < 0) return false;
        if (state.tickerFilter === "drawdown" && (t.currentDrawdownPct || 0) > -8) return false;
        if (state.tickerFilter === "crowded" && (t.shortPctFloat || 0) < 10 && (t.shortVolumeRatioPct || 0) < 50) return false;
        if (state.tickerFilter === "cycle_hot" && (t.technicalHeatScore || 0) < 80) return false;
        if (state.tickerFilter === "cycle_washout" && (t.technicalWashoutScore || 0) < 80) return false;
        if (state.tickerFilter === "cycle_extreme" && (t.technicalExtremeScore || 0) < 75) return false;
        return true;
      });
      rows = rankCandidateRows(rows, state.candidateMode);
      const rankMode = candidateModeDefs[state.candidateMode] || candidateModeDefs.balanced;
      const topCandidate = rows.slice().sort((a, b) => a.candidateRank - b.candidateRank)[0];
      const medianCoverage = avg(rows.map(t => t.candidateCoveragePct)) ?? 0;
      const activeInputCount = activeCandidateMetrics().length;
      const heatmapColumns = candidateHeatmapColumns();
      const distStats = mrrDistributionStats(rows);
      const topDistributionNames = rows.slice().sort((a, b) => b.candidateScore - a.candidateScore).slice(0, 5).map(row => row.ticker).join(", ");
      const topCycle = rows.slice().filter(t => isNum(t.technicalExtremeScore)).sort((a, b) => b.technicalExtremeScore - a.technicalExtremeScore)[0];
      rows.sort((a, b) => {
        const key = state.tickerSort === "activeScore" ? scoreKey : state.tickerSort;
        const dir = state.tickerDir === "asc" ? 1 : -1;
        return ((a[key] ?? -9999) - (b[key] ?? -9999)) * dir;
      });
      document.getElementById("view-root").innerHTML = `
        <section class="grid">
          <div class="panel">
            <div class="panel-head">
              <div><h2>Candidate Ranker</h2><p class="subtle">${rankMode.description}</p></div>
              ${candidateModeButtons()}
            </div>
            <div class="panel-body">
              <div class="candidate-workbench">
                <div class="rank-summary ${state.candidateCalcStatus === "current" && state.candidateInputMessage ? "mrr-flash" : ""}">
                  <div class="stat"><div class="tile-label">Top candidate</div><div class="value">${topCandidate?.ticker || "n/a"}</div><p class="subtle">${topCandidate ? `#${topCandidate.candidateRank} | MRR ${topCandidate.candidateScore.toFixed(0)}` : "No rankable rows"}</p></div>
                  <div class="stat"><div class="tile-label">Matching tickers</div><div class="value">${rows.length}</div><p class="subtle">${state.tickerSector === "all" ? "Full analyzed universe" : basketById.get(state.tickerSector)?.short || state.tickerSector}</p></div>
                  <div class="stat"><div class="tile-label">Rank mode</div><div class="value">${rankMode.label}</div><p class="subtle">${activeInputCount} active inputs</p></div>
                  <div class="stat"><div class="tile-label">Cycle extreme</div><div class="value">${topCycle?.ticker || "n/a"}</div><p class="subtle">${topCycle ? `${topCycle.technicalExtremeScore.toFixed(0)} | ${escapeHtml(topCycle.cyclicalState || "n/a")}` : "RSI/range history"}</p></div>
                </div>
                <div class="candidate-cockpit">
                  ${renderMrrInputPanel(rows)}
                  <div class="mrr-distribution-panel">
                    <div class="mrr-distribution-head">
                      <div><h2>MRR Distribution</h2><p class="subtle">Current score distribution after the active MRR input calculation</p></div>
                      <button class="small-btn" data-action="toggle-mrr-distribution">${state.showMrrDistribution ? "Hide distribution" : "Show distribution"}</button>
                    </div>
                    ${state.showMrrDistribution ? `
                      <div class="mrr-distribution-layout">
                        <div class="mrr-dist-stats">
                          <div class="mrr-dist-stat"><div class="tile-label">Median</div><div class="value">${isNum(distStats?.median) ? distStats.median.toFixed(0) : "n/a"}</div><p class="subtle">middle MRR</p></div>
                          <div class="mrr-dist-stat"><div class="tile-label">Top decile</div><div class="value">${isNum(distStats?.p90) ? distStats.p90.toFixed(0) : "n/a"}</div><p class="subtle">90th percentile</p></div>
                          <div class="mrr-dist-stat"><div class="tile-label">Spread</div><div class="value">${isNum(distStats?.spread) ? distStats.spread.toFixed(0) : "n/a"}</div><p class="subtle">${isNum(distStats?.min) && isNum(distStats?.max) ? `${distStats.min.toFixed(0)} to ${distStats.max.toFixed(0)}` : "n/a"}</p></div>
                          <div class="mrr-dist-stat"><div class="tile-label">Tickers</div><div class="value">${distStats?.n ?? 0}</div><p class="subtle">${activeInputCount} inputs</p></div>
                          <div class="mrr-dist-note">Bars are the actual scores. KDE is a smoothed guide bounded to 0-100. Current top names: ${escapeHtml(topDistributionNames || "n/a")}.</div>
                        </div>
                        <div class="chart mrr-dist-chart" id="mrr-distribution"></div>
                      </div>
                    ` : `<div class="empty">MRR distribution hidden for this session.</div>`}
                  </div>
                </div>
                <div class="candidate-command-bar">
                  <input class="input" id="ticker-search" placeholder="Search ticker or company" value="${state.tickerSearch.replaceAll('"', "&quot;")}" style="max-width:280px">
                  <select id="ticker-sector" style="max-width:220px">
                    <option value="all">All sectors</option>
                    ${baskets.map(m => `<option value="${m.basket}" ${state.tickerSector === m.basket ? "selected" : ""}>${m.label}</option>`).join("")}
                  </select>
                  ${[["all","All"],["positive","Positive"],["drawdown","Pullbacks"],["crowded","Crowded"],["cycle_hot","Cycle Hot"],["cycle_washout","Washed Out"],["cycle_extreme","Abnormal Cycle"]].map(([id,label]) => `<button class="chip ${state.tickerFilter === id ? "active" : ""}" data-action="ticker-filter" data-filter="${id}">${label}</button>`).join("")}
                  <button class="chip ${state.tickerSort === "candidateScore" ? "active" : ""}" data-action="sort-ticker" data-key="candidateScore">Sort MRR score</button>
                  <button class="chip ${state.tickerSort === "technicalExtremeScore" ? "active" : ""}" data-action="sort-ticker" data-key="technicalExtremeScore">Sort cycle</button>
                  <button class="chip ${state.tickerSort === "rsi14Percentile" ? "active" : ""}" data-action="sort-ticker" data-key="rsi14Percentile">Sort RSI pctl</button>
                </div>
                <div class="candidate-table-shell">
                  <div class="candidate-table-head">
                    <div><h3>Ranked Universe</h3><p class="subtle">Click a row for chart, positioning, technicals, and fundamentals.</p></div>
                    <p class="subtle">${rows.length} rows | ${activeInputCount} active rank inputs</p>
                  </div>
                  ${tickerTable(rows, "global")}
                </div>
              </div>
            </div>
          </div>
          <div class="panel">
            <div class="panel-head"><div><h2>Candidate Heatmap</h2><p class="subtle">Top candidates by the active rank mode with a plain-English reference</p></div></div>
            <div class="panel-body"><div id="candidate-heatmap"></div>${heatmapReference(heatmapColumns)}</div>
          </div>
        </section>
      `;
      if (state.showMrrDistribution) mrrDistributionChart("mrr-distribution", rows, { compact: true });
      renderHeatmap("candidate-heatmap", rows.slice().sort((a, b) => a.candidateRank - b.candidateRank).slice(0, 20), heatmapColumns);
      const search = document.getElementById("ticker-search");
      search?.addEventListener("input", e => { state.tickerSearch = e.target.value; renderTickers(); });
      const sector = document.getElementById("ticker-sector");
      sector?.addEventListener("change", e => { state.tickerSector = e.target.value; renderTickers(); });
    }

    function activeSetupCategory() {
      return state.setupState?.categories?.find(category => category.id === state.setupCategory) || state.setupState?.categories?.[0] || null;
    }

    function coverageDots(coverage = {}) {
      const labels = [
        ["price", "Price"],
        ["fundamentals", "Fund"],
        ["options", "Opt"],
        ["shortInterest", "Short interest"],
        ["institutional", "Inst"]
      ];
      return `<div class="coverage-dots">${labels.map(([key, label]) => `<span title="${label}" class="coverage-dot ${coverage[key] ? "good" : ""}"></span>`).join("")}</div>`;
    }

    function renderRunStatus() {
      const run = state.runStatus || state.setupState?.run || {};
      const log = (run.log || []).slice(-80).map(escapeHtml).join("\\n");
      return `
        <div class="metric-row"><span>Status</span><strong>${escapeHtml(run.state || "idle")}</strong></div>
        <div class="metric-row"><span>Run id</span><strong>${escapeHtml(run.runId || "n/a")}</strong></div>
        <div class="metric-row"><span>Started</span><strong>${escapeHtml(run.startedAt || "n/a")}</strong></div>
        <div class="metric-row"><span>Finished</span><strong>${escapeHtml(run.finishedAt || "n/a")}</strong></div>
        <div class="run-log">${log || "No run log yet."}</div>
      `;
    }

    function taxonomyPathLabel(path) {
      return (path || []).length ? path.join(" > ") : "Unclassified";
    }

    function contextSourceBadges(row) {
      const sources = row.contextSources || [];
      if (!sources.length) return `<span class="source-badge">local only</span>`;
      return `<div class="source-badges">${sources.map(source => {
        const status = source.status || "missing";
        const cls = status === "ok" || status === "partial" ? "ok" : status === "error" ? "error" : "";
        const label = `${source.source || "source"}:${status}`;
        return `<span class="source-badge ${cls}" title="${escapeHtml(source.error || source.url || "")}">${escapeHtml(label)}</span>`;
      }).join("")}</div>`;
    }

    function renderTickerIntake() {
      const categories = state.setupState?.categories || [];
      const openai = state.openaiStatus || {};
      const hasKey = openai.hasSessionKey || openai.hasEnvKey;
      return `
        <div class="panel">
          <div class="panel-head">
            <div><h2>Ticker Intake</h2><p class="subtle">Paste tickers or natural language, classify them into the layered taxonomy, then approve before config changes.</p></div>
            <span class="pending-note">${hasKey ? "OpenAI ready" : "OpenAI key needed"}</span>
          </div>
          <div class="panel-body grid">
            <div class="intake-panel">
              <div class="grid">
                <label>
                  <div class="tile-label">Ticker text</div>
                  <textarea class="input" id="ticker-intake-text" rows="7" placeholder="RGTI, QBTS, NTR, MOS, CF, SMR, ASML">${escapeHtml(state.intakeText)}</textarea>
                </label>
                <div class="compare-strip">
                  <button class="small-btn" data-action="intake-parse" ${state.intakeBusy ? "disabled" : ""}>Parse Tickers</button>
                  <button class="small-btn" data-action="intake-context" ${state.intakeBusy ? "disabled" : ""}>Fetch Web Context</button>
                  <button class="primary-btn" data-action="intake-classify" ${state.intakeBusy ? "disabled" : ""}>Classify With OpenAI</button>
                  <button class="small-btn" data-action="intake-add" ${state.intakeBusy || !state.intakeRows.some(row => row.selected) ? "disabled" : ""}>Add Selected</button>
                </div>
                <div class="intake-status">
                  <strong>${escapeHtml(openai.model || state.openaiModel)}</strong>
                  <span>${openai.hasSessionKey ? "session key active" : openai.hasEnvKey ? "using OPENAI_API_KEY env var" : "no key active"}</span>
                  <span>${state.intakeRows.length} parsed row(s)</span>
                </div>
              </div>
              <div class="grid">
                <div class="intake-key-grid">
                  <label>
                    <div class="tile-label">OpenAI key</div>
                    <input class="input" id="openai-key" type="password" autocomplete="off" placeholder="sk-...">
                  </label>
                  <label>
                    <div class="tile-label">Model</div>
                    <input class="input" id="openai-model" value="${escapeHtml(openai.model || state.openaiModel)}">
                  </label>
                  <button class="small-btn" data-action="openai-save-key">Use Key</button>
                  <button class="small-btn" data-action="openai-forget-key">Forget</button>
                </div>
                <div class="footnote">Key handling: browser sends the key only to this local server; the server keeps it in memory and never writes it into config, generated HTML, logs, or CSV outputs. It disappears when the server stops or when you click Forget.</div>
                ${state.intakeMessage ? `<div class="warning">${escapeHtml(state.intakeMessage)}</div>` : ""}
              </div>
            </div>
            <div class="table-wrap">
              <table class="intake-table">
                <thead>
                  <tr><th>Add</th><th>Ticker</th><th>Name</th><th>Recommended basket</th><th>Taxonomy path</th><th>Confidence</th><th>Context</th><th>Note / rationale</th></tr>
                </thead>
                <tbody>
                  ${state.intakeRows.length ? state.intakeRows.map(row => `
                    <tr>
                      <td><input type="checkbox" data-intake-field="selected" data-ticker="${escapeHtml(row.ticker)}" ${row.selected ? "checked" : ""} ${row.alreadyInConfig || row.recommendedBasket === "unclassified" ? "disabled" : ""}></td>
                      <td><strong>${escapeHtml(row.ticker)}</strong><div class="subtle">${escapeHtml(row.validationStatus || "")}${row.alreadyInConfig ? " | already configured" : ""}</div></td>
                      <td><input type="text" data-intake-field="companyName" data-ticker="${escapeHtml(row.ticker)}" value="${escapeHtml(row.companyName || row.ticker)}"></td>
                      <td>
                        <select data-intake-field="recommendedBasket" data-ticker="${escapeHtml(row.ticker)}">
                          <option value="unclassified" ${row.recommendedBasket === "unclassified" || !row.recommendedBasket ? "selected" : ""}>Unclassified</option>
                          ${categories.map(category => `<option value="${category.id}" ${row.recommendedBasket === category.id ? "selected" : ""}>${escapeHtml(category.label)}</option>`).join("")}
                        </select>
                      </td>
                      <td><span class="path-pill">${escapeHtml(taxonomyPathLabel(row.taxonomyPath || categories.find(c => c.id === row.recommendedBasket)?.taxonomyPath))}</span></td>
                      <td class="mono">${isNum(row.confidence) ? `${Math.round(row.confidence * 100)}%` : "n/a"}<div class="confidence-meter"><span style="width:${clamp((row.confidence || 0) * 100)}%"></span></div></td>
                      <td>
                        ${contextSourceBadges(row)}
                        <div class="why">${escapeHtml([row.sector, row.industry].filter(Boolean).join(" | ") || row.externalContextStatus || "local cache only")}</div>
                        ${row.businessSummary ? `<div class="footnote">${escapeHtml(row.businessSummary.slice(0, 220))}${row.businessSummary.length > 220 ? "..." : ""}</div>` : ""}
                      </td>
                      <td>
                        <input type="text" data-intake-field="suggestedNote" data-ticker="${escapeHtml(row.ticker)}" value="${escapeHtml(row.suggestedNote || row.localNote || "")}">
                        <div class="why">${escapeHtml(row.rationale || "")}</div>
                      </td>
                    </tr>
                  `).join("") : `<tr><td colspan="8"><div class="empty">Paste tickers, parse, fetch web context, then classify.</div></td></tr>`}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      `;
    }

    function renderSetup() {
      const root = document.getElementById("view-root");
      if (!state.setupAvailable || !state.setupState) {
        root.innerHTML = `
          <section class="grid">
            <div class="panel">
              <div class="panel-head"><div><h2>Run & Universe</h2><p class="subtle">Start the local workbench server to edit the universe and run the full analysis.</p></div></div>
              <div class="panel-body grid">
                <div class="warning">Run <strong>python3 workbench_server.py 8124</strong>, then open <strong>http://127.0.0.1:8124/market-basket-analyst-workstation.html</strong>. Static file serving cannot update config or run the pipeline.</div>
                <button class="small-btn" data-action="setup-refresh">Reconnect</button>
              </div>
            </div>
          </section>
        `;
        return;
      }
      const category = activeSetupCategory();
      const startDate = state.setupState.methodology?.startDate || DATA.methodology.startDate;
      const endDate = state.setupState.methodology?.endDate || DATA.methodology.endDate;
      const priceRefresh = state.setupState.priceRefresh || {};
      const sourceGaps = priceRefresh.sourceHistoryGaps || [];
      const sourceGapText = sourceGaps.slice(0, 4).map(gap => `${gap.ticker} starts ${gap.firstDate}`).join("; ");
      root.innerHTML = `
        <section class="grid">
          <div class="panel">
            <div class="panel-head">
              <div><h2>Analysis Window</h2><p class="subtle">Set the study window, then rerun the full universe.</p></div>
              ${state.pendingChanges ? `<span class="pending-note">Changes pending. Run Full Analysis to apply.</span>` : ""}
            </div>
            <div class="panel-body grid">
              <div class="stat-grid">
                <label class="stat">
                  <div class="tile-label">Start date</div>
                  <input class="input" id="setup-start-date" type="date" value="${escapeHtml(startDate)}" max="${escapeHtml(endDate)}">
                </label>
                <div class="stat"><div class="tile-label">End date</div><div class="value">${escapeHtml(endDate)}</div><p class="subtle">Latest configured date</p></div>
                <div class="stat"><div class="tile-label">Current baskets</div><div class="value">${state.setupState.categories.length}</div><p class="subtle">Full universe reruns together</p></div>
                <div class="stat"><div class="tile-label">QA</div><div class="value">${DATA.qa?.status || "n/a"}</div><p class="subtle">${DATA.qa?.summary?.warnings ?? 0} warnings</p></div>
              </div>
              <div class="compare-strip">
                <button class="small-btn" data-action="setup-save-start">Save start date</button>
                <button class="primary-btn" data-action="setup-run" ${state.runStatus?.running ? "disabled" : ""}>Run Full Analysis</button>
              </div>
              <details class="refresh-options">
                <summary>Advanced refresh options</summary>
                <div class="compare-strip">
                  ${[
                    ["refreshPrices", "Fresh prices"],
                    ["refreshFundamentals", "Fresh fundamentals"],
                    ["refreshPositioning", "Fresh options/short volume"],
                    ["refreshOwnership", "Fresh short interest/institutional"]
                  ].map(([key, label]) => `<button class="chip ${state[key] ? "active" : ""}" data-action="toggle-refresh" data-key="${key}">${label}</button>`).join("")}
                </div>
                <div class="footnote">Default run recomputes the full analysis from cached inputs. Use fresh prices after adding new tickers that are not cached.</div>
              </details>
              ${priceRefresh.required ? `<div class="warning"><strong>Fresh prices will be included automatically.</strong> ${escapeHtml((priceRefresh.reasons || []).join(" "))}</div>` : ""}
              ${sourceGaps.length ? `<div class="warning"><strong>Source history gaps:</strong> ${escapeHtml(sourceGapText)}${sourceGaps.length > 4 ? "..." : ""}. Late-listed/relisted tickers join the basket after their first return observation.</div>` : ""}
              ${state.setupMessage ? `<div class="warning">${escapeHtml(state.setupMessage)}</div>` : ""}
              ${renderRunStatus()}
            </div>
          </div>

          ${renderTickerIntake()}

          <section class="setup-grid">
            <div class="panel">
              <div class="panel-head"><div><h2>Basket Universe</h2><p class="subtle">Pick a basket to edit. The analysis run still applies to every basket.</p></div></div>
              <div class="panel-body grid">
                <label>
                  <div class="tile-label">Basket to edit</div>
                  <select id="setup-category">
                    ${state.setupState.categories.map(c => `<option value="${c.id}" ${c.id === category?.id ? "selected" : ""}>${escapeHtml(c.label)}</option>`).join("")}
                  </select>
                </label>
                <div class="warning">${escapeHtml(category?.description || "")}</div>
                <div class="panel flat">
                  <div class="panel-head"><div><h3>${escapeHtml(category?.label || "Basket")} Holdings</h3><p class="subtle">${category?.holdings?.length || 0} current tickers</p></div></div>
                  <div class="panel-body">
                <div class="mini-bars">
                  ${(category?.holdings || []).map(row => `<div class="list-row">
                    <div><strong>${escapeHtml(row.ticker)}</strong><span class="subtle"> ${escapeHtml(row.name)} | ${escapeHtml(row.note)}</span></div>
                    <button class="small-btn" data-action="setup-remove" data-ticker="${escapeHtml(row.ticker)}">Remove</button>
                  </div>`).join("")}
                </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="panel">
              <div class="panel-head"><div><h2>Approved Candidate Search</h2><p class="subtle">Search eligible tickers for the selected basket. Random tickers are filtered out by the taxonomy.</p></div></div>
              <div class="panel-body">
                <div class="filter-row" style="margin-bottom:12px">
                  <input class="input" id="setup-search" placeholder="Search approved ${escapeHtml(category?.short || "basket")} candidates" value="${escapeHtml(state.setupSearch)}" style="max-width:360px">
                  <button class="small-btn" data-action="setup-search">Search</button>
                </div>
                <div>
                  ${state.setupResults.length ? state.setupResults.map(row => `
                    <div class="candidate-card">
                      <div>
                        <strong>${escapeHtml(row.ticker)}</strong> <span class="subtle">${escapeHtml(row.name)}</span>
                        <div class="why">${escapeHtml(row.reason)}</div>
                        ${coverageDots(row.coverage)}
                      </div>
                      <button class="small-btn" data-action="setup-add" data-ticker="${escapeHtml(row.ticker)}" ${row.alreadyInBasket ? "disabled" : ""}>${row.alreadyInBasket ? "In basket" : "Add"}</button>
                    </div>
                  `).join("") : `<div class="empty">Search the selected basket to add eligible tickers.</div>`}
                </div>
              </div>
            </div>
          </section>
        </section>
      `;
      document.getElementById("setup-category")?.addEventListener("change", e => {
        state.setupCategory = e.target.value;
        state.setupSearch = "";
        state.setupResults = [];
        renderSetup();
        searchSetupCandidates();
      });
      document.getElementById("setup-search")?.addEventListener("input", e => { state.setupSearch = e.target.value; });
      document.getElementById("ticker-intake-text")?.addEventListener("input", e => { state.intakeText = e.target.value; });
      document.getElementById("openai-model")?.addEventListener("input", e => { state.openaiModel = e.target.value; });
    }

    function reviewFileHref(path) {
      if (!path) return "";
      const idx = String(path).indexOf("/data/");
      return idx >= 0 ? String(path).slice(idx + 1) : String(path);
    }

    function renderPortfolioReview() {
      const root = document.getElementById("view-root");
      const review = state.portfolioReview;
      const diagnostics = review?.diagnostics || [];
      const recommendations = review?.top_recommendations || review?.recommendations || [];
      const freshness = review?.freshness || {};
      const files = review?.files || {};
      root.innerHTML = `
        <section class="grid">
          <div class="panel">
            <div class="panel-head">
              <div>
                <h2>Portfolio Review</h2>
                <p class="subtle">Button-triggered mechanical review for the app-metrics and web-metrics paper portfolios.</p>
              </div>
              <div class="compare-strip">
                <label class="chip">
                  <span>Goal</span>
                  <input id="portfolio-review-goal" type="number" step="0.1" min="-5" max="10" value="${escapeHtml(state.portfolioReviewGoal)}" style="width:72px; border:0; background:transparent">
                  <span>% / wk</span>
                </label>
                <button class="chip ${state.portfolioReviewRefreshData ? "active" : ""}" data-action="portfolio-review-toggle-refresh">Refresh data</button>
                <button class="primary-btn" data-action="portfolio-review-run" ${state.portfolioReviewBusy ? "disabled" : ""}>Run Portfolio Review</button>
              </div>
            </div>
            <div class="panel-body grid">
              ${state.portfolioReviewMessage ? `<div class="warning">${escapeHtml(state.portfolioReviewMessage)}</div>` : ""}
              <div class="stat-grid">
                <div class="stat"><div class="tile-label">Last run</div><div class="value">${escapeHtml(review?.date || "none")}</div><p class="subtle">${escapeHtml(review?.run_id || "No review generated yet")}</p></div>
                <div class="stat"><div class="tile-label">Goal</div><div class="value">${review?.goal ? fmtPct(review.goal.weekly_return_pct) : fmtPct(state.portfolioReviewGoal)}</div><p class="subtle">Weekly target</p></div>
                <div class="stat"><div class="tile-label">Freshness</div><div class="value">${escapeHtml(freshness.status || "n/a")}</div><p class="subtle">${(freshness.missing || []).length} missing inputs</p></div>
                <div class="stat"><div class="tile-label">LLM</div><div class="value">${escapeHtml(review?.llm?.mode || "placeholder")}</div><p class="subtle">${escapeHtml(review?.llm?.authority || "journal only")}</p></div>
              </div>
            </div>
          </div>

          <div class="grid two-col">
            <div class="panel">
              <div class="panel-head"><div><h2>Portfolio Diagnostics</h2><p class="subtle">Goal gap and exposure by paper portfolio</p></div></div>
              <div class="panel-body">
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Portfolio</th><th>Value</th><th>Exposure</th><th>Cash</th><th>Weekly</th><th>Target Gap</th><th>Positions</th></tr></thead>
                    <tbody>
                      ${diagnostics.length ? diagnostics.map(row => `<tr>
                        <td><strong>${escapeHtml(row.portfolio_id)}</strong></td>
                        <td class="mono">$${fmtNum(row.portfolio_value)}</td>
                        <td class="mono">${fmtPct(row.gross_exposure_pct)}</td>
                        <td class="mono">$${fmtNum(row.cash_reserve)}</td>
                        <td class="mono ${cls(row.weekly_return_pct)}">${fmtPct(row.weekly_return_pct)}</td>
                        <td class="mono">${fmtPct(row.target_gap_pct)}</td>
                        <td class="mono">${fmtNum(row.position_count)}</td>
                      </tr>`).join("") : `<tr><td colspan="7"><div class="empty">Run a portfolio review to populate diagnostics.</div></td></tr>`}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div class="panel">
              <div class="panel-head"><div><h2>Review Files</h2><p class="subtle">Durable audit trail for automation and journal review</p></div></div>
              <div class="panel-body">
                ${review ? `<div class="mini-bars">
                  ${[
                    ["Recommendations", files.recommendations],
                    ["Decision audit", files.decision_audit],
                    ["Feature snapshot", files.feature_snapshot],
                    ["Journal", files.journal]
                  ].map(([label, path]) => `<div class="list-row"><strong>${label}</strong>${path ? `<a class="small-btn" href="${escapeHtml(reviewFileHref(path))}" target="_blank" rel="noreferrer">Open</a>` : "<span>n/a</span>"}</div>`).join("")}
                </div>` : `<div class="empty">No review files yet.</div>`}
              </div>
            </div>
          </div>

          <div class="panel">
            <div class="panel-head">
              <div><h2>CSV Portfolio Import</h2><p class="subtle">Autopopulate tickers, buy dates, shares, prices, values, and notes from a portfolio CSV.</p></div>
              <button class="small-btn" data-action="portfolio-import-csv">Import CSV</button>
            </div>
            <div class="panel-body grid">
              <div class="filter-row">
                <label>
                  <div class="tile-label">Portfolio id</div>
                  <input class="input" id="portfolio-import-id" value="${escapeHtml(state.portfolioImportId)}" style="max-width:260px">
                </label>
                <label>
                  <div class="tile-label">Upload CSV</div>
                  <input class="input" id="portfolio-import-file" type="file" accept=".csv,text/csv">
                </label>
              </div>
              <textarea class="input" id="portfolio-import-text" rows="6" placeholder="Ticker,Buy Date,Quantity,Price,Notes">${escapeHtml(state.portfolioImportText)}</textarea>
              ${state.portfolioImportMessage ? `<div class="warning">${escapeHtml(state.portfolioImportMessage)}</div>` : ""}
            </div>
          </div>

          <div class="panel" id="review-recommendations">
            <div class="panel-head"><div><h2>Recommended Changes</h2><p class="subtle">Mechanical rows only; intuition is logged separately and cannot move weights yet.</p></div></div>
            <div class="panel-body">
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Portfolio</th><th>Ticker</th><th>Action</th><th>Current</th><th>Recommended</th><th>Change</th><th>Confidence</th><th>Evidence</th><th>Intuition</th></tr></thead>
                  <tbody>
                    ${recommendations.length ? recommendations.map(row => `<tr>
                      <td>${escapeHtml(row.portfolio_id)}</td>
                      <td><strong>${escapeHtml(row.ticker)}</strong><div class="why">${escapeHtml(row.group || "")}</div></td>
                      <td><span class="score-pill">${escapeHtml(row.action)}</span></td>
                      <td class="mono">${fmtPct(row.current_weight_pct)}</td>
                      <td class="mono">${fmtPct(row.recommended_weight_pct)}</td>
                      <td class="mono ${cls(row.weight_change_pct)}">${fmtPct(row.weight_change_pct)}</td>
                      <td class="mono">${fmtNum(row.confidence_score)}</td>
                      <td>${escapeHtml(row.evidence_summary)}</td>
                      <td>${escapeHtml(row.intuition_summary)}</td>
                    </tr>`).join("") : `<tr><td colspan="9"><div class="empty">Run a portfolio review to generate recommended changes.</div></td></tr>`}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      `;
      document.getElementById("portfolio-review-goal")?.addEventListener("input", e => { state.portfolioReviewGoal = Number(e.target.value || 1); });
      document.getElementById("portfolio-import-id")?.addEventListener("input", e => { state.portfolioImportId = e.target.value; });
      document.getElementById("portfolio-import-text")?.addEventListener("input", e => { state.portfolioImportText = e.target.value; });
      document.getElementById("portfolio-import-file")?.addEventListener("change", async e => {
        const file = e.target.files?.[0];
        if (!file) return;
        state.portfolioImportText = await file.text();
        renderPortfolioReview();
      });
    }

    function renderData() {
      const qaWarnings = DATA.qa?.warnings || [];
      const covRows = baskets.slice().sort((a, b) => a.coverageScore - b.coverageScore);
      document.getElementById("view-root").innerHTML = `
        <section class="grid">
          <div class="quality-grid">
            <div class="quality-card"><div class="tile-label">QA status</div><div class="tile-value">${DATA.qa?.status || "n/a"}</div><p class="subtle">${DATA.qa?.summary?.errors || 0} errors</p></div>
            <div class="quality-card"><div class="tile-label">Warnings</div><div class="tile-value">${qaWarnings.length}</div><p class="subtle">Shown below</p></div>
            <div class="quality-card"><div class="tile-label">Price rows</div><div class="tile-value">${DATA.qa?.summary?.advanced_price_rows || "n/a"}</div><p class="subtle">Advanced metrics</p></div>
            <div class="quality-card"><div class="tile-label">Institutional rows</div><div class="tile-value">${DATA.qa?.summary?.institutional_full_rows || "n/a"}</div><p class="subtle">13F snapshots</p></div>
          </div>
          <div class="grid two-col">
            <div class="panel">
              <div class="panel-head"><div><h2>Coverage Matrix</h2><p class="subtle">Lower confidence sectors need more source work before sizing decisions</p></div></div>
              <div class="panel-body">
                <div class="mini-bars">
                  ${covRows.map(m => `<div class="mini-bar">
                    <span>${m.short}</span>
                    <div class="bar-track"><div class="bar-fill" style="width:${clamp(m.coverageScore)}%; background:${m.coverageScore >= 75 ? "var(--green)" : m.coverageScore >= 50 ? "var(--amber)" : "var(--red)"}"></div></div>
                    <span class="mono">${m.coverageScore.toFixed(0)}</span>
                  </div>`).join("")}
                </div>
              </div>
            </div>
            <div class="panel">
              <div class="panel-head"><div><h2>QA Notes</h2><p class="subtle">Pipeline caveats from the latest run</p></div></div>
              <div class="panel-body grid">
                ${qaWarnings.length ? qaWarnings.map(w => `<div class="warning">${w}</div>`).join("") : `<div class="empty">No warnings</div>`}
              </div>
            </div>
          </div>
          <div class="panel">
            <div class="panel-head"><div><h2>Source Status</h2><p class="subtle">Latest price source metadata by ticker</p></div></div>
            <div class="panel-body">
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Ticker</th><th>Instrument</th><th>Exchange</th><th>Last price date</th><th>Rows</th><th>Source symbol</th></tr></thead>
                  <tbody>
                    ${Object.entries(DATA.sourceMetadata || {}).slice().sort(([a],[b]) => a.localeCompare(b)).map(([ticker, s]) => `<tr>
                      <td><strong>${ticker}</strong></td><td>${s.instrumentType || ""}</td><td>${s.exchange || ""}</td><td>${s.lastDate || ""}</td><td class="mono">${s.rowCount || ""}</td><td>${s.sourceSymbol || ""}</td>
                    </tr>`).join("")}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      `;
    }

    function openTicker(ticker) {
      const t = tickers.find(x => x.ticker === ticker);
      if (!t) return;
      state.openTicker = ticker;
      const source = DATA.sourceMetadata?.[ticker] || {};
      const drawer = document.getElementById("ticker-drawer");
      drawer.innerHTML = `
        <div class="drawer-head">
          <div>
            <h2>${t.ticker}</h2>
            <p class="subtle">${t.name}</p>
          </div>
          <button class="icon-btn" data-action="close-drawer">Close</button>
        </div>
        <div class="drawer-body grid">
          <div class="stat-grid">
            <div class="stat"><div class="tile-label">Return</div><div class="value ${cls(t.returnPct)}">${fmtPct(t.returnPct)}</div></div>
            <div class="stat"><div class="tile-label">20D</div><div class="value ${cls(t.return20dPct)}">${fmtPct(t.return20dPct)}</div></div>
            <div class="stat"><div class="tile-label">Drawdown</div><div class="value ${cls(t.currentDrawdownPct)}">${fmtPct(t.currentDrawdownPct)}</div></div>
            <div class="stat"><div class="tile-label">Short Interest % Float</div><div class="value">${fmtPct(t.shortPctFloat)}</div></div>
          </div>
          <div class="chart micro" id="drawer-line"></div>
          <div class="panel flat">
            <div class="panel-head"><div><h3>Positioning / Sponsorship</h3></div></div>
            <div class="panel-body">
              <div class="metric-row"><span>Short volume</span><strong>${fmtPct(t.shortVolumeRatioPct)}</strong></div>
              <div class="metric-row"><span>Put/call open interest</span><strong>${fmtNum(t.putCallOpenInterestRatio)}</strong></div>
              <div class="metric-row"><span>Institutional ownership</span><strong>${fmtPct(t.institutionalOwnershipPct)}</strong></div>
              <div class="metric-row"><span>Institutional QoQ</span><strong class="${cls(t.institutionalSharesChangedQoqPct)}">${fmtPct(t.institutionalSharesChangedQoqPct)}</strong></div>
            </div>
          </div>
          <div class="panel flat">
            <div class="panel-head"><div><h3>Cyclical Technicals</h3><p class="subtle">${cycleBadge(t.cyclicalState)} ${t.cyclicalLookbackCount ? `${t.cyclicalLookbackCount} RSI observations` : ""}</p></div></div>
            <div class="panel-body">
              <div class="metric-row"><span>Cycle extreme score</span><strong>${isNum(t.technicalExtremeScore) ? t.technicalExtremeScore.toFixed(0) : "n/a"}</strong></div>
              <div class="metric-row"><span>RSI 14 / percentile</span><strong>${isNum(t.rsi14) ? t.rsi14.toFixed(1) : "n/a"} / ${fmtPctile(t.rsi14Percentile)}</strong></div>
              <div class="metric-row"><span>Stoch RSI / percentile</span><strong>${isNum(t.stochRsi14) ? t.stochRsi14.toFixed(0) : "n/a"} / ${fmtPctile(t.stochRsi14Percentile)}</strong></div>
              <div class="metric-row"><span>20DMA stretch / z</span><strong>${fmtPct(t.distanceFrom20dmaPct)} / ${fmtNum(t.distanceFrom20dmaZscore)}</strong></div>
              <div class="metric-row"><span>5D return z / volume z</span><strong>${fmtNum(t.return5dZscore)} / ${fmtNum(t.volumeZscore20d)}</strong></div>
              <div class="metric-row"><span>Realized vol percentile</span><strong>${fmtPctile(t.realizedVol20dPercentile)}</strong></div>
            </div>
          </div>
          <div class="panel flat">
            <div class="panel-head"><div><h3>Fundamentals</h3></div></div>
            <div class="panel-body">
              <div class="metric-row"><span>Revenue growth</span><strong class="${cls(t.revenueGrowthYoyPct)}">${fmtPct(t.revenueGrowthYoyPct)}</strong></div>
              <div class="metric-row"><span>Operating margin</span><strong class="${cls(t.operatingMarginPct)}">${fmtPct(t.operatingMarginPct)}</strong></div>
              <div class="metric-row"><span>Free cash flow margin</span><strong class="${cls(t.freeCashFlowMarginPct)}">${fmtPct(t.freeCashFlowMarginPct)}</strong></div>
              <div class="metric-row"><span>Net cash</span><strong>${fmtNum(t.netCash)}</strong></div>
            </div>
          </div>
          <div class="footnote">
            Price source: ${source.instrumentType || "n/a"} ${source.exchange || ""} | last price date ${source.lastDate || "n/a"} | fundamentals ${t.fundamentalsStatus || "n/a"} | institutional ${t.institutionalStatus || "n/a"}.
          </div>
        </div>
      `;
      drawer.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
      lineChart("drawer-line", [{ name: t.ticker, color: (t.baskets || [])[0]?.color || "var(--green)", points: (t.series || []).map(p => ({ date: p.date, value: p.value })) }], { height: 160 });
    }

    function closeDrawer() {
      const drawer = document.getElementById("ticker-drawer");
      drawer.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
      state.openTicker = null;
    }

    function renderCurrentRankerView() {
      if (state.view === "sector") renderSector();
      else if (state.view === "tickers") renderTickers();
      else render();
    }

    function render() {
      document.querySelectorAll(".nav [data-view]").forEach(btn => btn.classList.toggle("active", btn.dataset.view === state.view));
      const lensWrap = document.querySelector(".lens-wrap");
      if (lensWrap) lensWrap.style.display = state.view === "overview" ? "flex" : "none";
      renderLensControls();
      if (state.view === "overview") renderOverview();
      if (state.view === "compare") renderCompare();
      if (state.view === "sector") renderSector();
      if (state.view === "tickers") renderTickers();
      if (state.view === "portfolio-review") renderPortfolioReview();
      if (state.view === "setup") renderSetup();
      if (state.view === "data") renderData();
    }

    document.addEventListener("change", e => {
      const field = e.target.closest("[data-intake-field]");
      if (!field) return;
      const ticker = field.dataset.ticker;
      const key = field.dataset.intakeField;
      const row = state.intakeRows.find(item => item.ticker === ticker);
      if (!row) return;
      if (key === "selected") row.selected = Boolean(field.checked);
      else {
        row[key] = field.value;
        if (key === "recommendedBasket") {
          const category = state.setupState?.categories?.find(item => item.id === field.value);
          row.taxonomyPath = category?.taxonomyPath || [];
          row.selected = field.value !== "unclassified" && !row.alreadyInConfig;
        }
      }
      renderSetup();
    });

    document.addEventListener("click", async e => {
      const el = e.target.closest("[data-action]");
      if (!el) return;
      const action = el.dataset.action;
      if (action === "view") {
        state.view = el.dataset.view;
        render();
        if (state.view === "setup") {
          await refreshWorkbenchState();
          if (state.setupAvailable) await searchSetupCandidates();
        }
        if (state.view === "portfolio-review") {
          await refreshPortfolioReview();
        }
      }
      if (action === "lens") {
        state.lens = el.dataset.lens;
        render();
      }
      if (action === "rank-mode") {
        state.candidateMode = el.dataset.mode;
        resetMrrInputs(state.candidateMode);
        markMrrCalculated(`MRR recalculated with ${candidateModeDefs[state.candidateMode]?.label || state.candidateMode} defaults at ${calcTime()}.`);
        state.sectorSort = "candidateScore";
        state.tickerSort = "candidateScore";
        state.sectorDir = "desc";
        state.tickerDir = "desc";
        renderCurrentRankerView();
      }
      if (action === "toggle-mrr-input") {
        const id = el.dataset.metric;
        const draft = new Set(state.candidateDraftMetricIds.length ? state.candidateDraftMetricIds : state.candidateActiveMetricIds);
        draft.has(id) ? draft.delete(id) : draft.add(id);
        state.candidateDraftMetricIds = candidateMetricCatalog.map(metric => metric.id).filter(metricId => draft.has(metricId));
        state.candidateInputsDirty = !sameMetricIds(state.candidateDraftMetricIds, state.candidateActiveMetricIds);
        state.candidateInputMessage = state.candidateDraftMetricIds.length ? "" : "Select at least one MRR input before recalculating.";
        state.candidateCalcStatus = state.candidateDraftMetricIds.length ? "pending" : "error";
        if (state.candidateInputsDirty && state.candidateDraftMetricIds.length) {
          state.candidateInputMessage = "MRR input draft changed. Existing scores are still based on the active inputs until Recalculate MRR is clicked.";
        }
        renderCurrentRankerView();
      }
      if (action === "apply-mrr-inputs") {
        if (!state.candidateDraftMetricIds.length) {
          state.candidateInputMessage = "Select at least one MRR input before recalculating.";
          state.candidateCalcStatus = "error";
          renderCurrentRankerView();
        } else {
          state.candidateCalcStatus = "calculating";
          state.candidateInputMessage = `Recalculating MRR in the browser using ${state.candidateDraftMetricIds.length} selected inputs...`;
          renderCurrentRankerView();
          await new Promise(resolve => setTimeout(resolve, 180));
          state.candidateActiveMetricIds = [...state.candidateDraftMetricIds];
          state.candidateInputsDirty = false;
          state.sectorSort = "candidateScore";
          state.tickerSort = "candidateScore";
          state.sectorDir = "desc";
          state.tickerDir = "desc";
          markMrrCalculated();
          renderCurrentRankerView();
        }
      }
      if (action === "reset-mrr-inputs") {
        resetMrrInputs(state.candidateMode);
        markMrrCalculated(`MRR reset and recalculated with ${candidateModeDefs[state.candidateMode]?.label || state.candidateMode} defaults at ${calcTime()}.`);
        state.sectorSort = "candidateScore";
        state.tickerSort = "candidateScore";
        state.sectorDir = "desc";
        state.tickerDir = "desc";
        renderCurrentRankerView();
      }
      if (action === "toggle-mrr-distribution") {
        state.showMrrDistribution = !state.showMrrDistribution;
        renderTickers();
      }
      if (action === "sector" || action === "select-sector") {
        state.selectedSector = el.dataset.sector;
        state.view = "sector";
        render();
      }
      if (action === "toggle-basket") {
        const id = el.dataset.sector;
        if (state.selectedBaskets.has(id)) {
          if (state.selectedBaskets.size > 1) state.selectedBaskets.delete(id);
        } else {
          state.selectedBaskets.add(id);
        }
        renderCompare();
      }
      if (action === "add-compare") {
        state.selectedBaskets.add(el.dataset.sector);
        state.view = "compare";
        render();
      }
      if (action === "bench") {
        const id = el.dataset.bench;
        state.showBenchmarks.has(id) ? state.showBenchmarks.delete(id) : state.showBenchmarks.add(id);
        renderCompare();
      }
      if (action === "sort-compare") {
        const key = el.dataset.key;
        if (state.compareSort === key) state.compareDir = state.compareDir === "desc" ? "asc" : "desc";
        state.compareSort = key;
        renderCompare();
      }
      if (action === "sort-sector") {
        const key = el.dataset.key;
        if (state.sectorSort === key) state.sectorDir = state.sectorDir === "desc" ? "asc" : "desc";
        else state.sectorDir = key === "candidateRank" ? "asc" : "desc";
        state.sectorSort = key;
        renderSector();
      }
      if (action === "sort-ticker") {
        const key = el.dataset.key;
        if (state.tickerSort === key) state.tickerDir = state.tickerDir === "desc" ? "asc" : "desc";
        else state.tickerDir = key === "candidateRank" ? "asc" : "desc";
        state.tickerSort = key;
        renderTickers();
      }
      if (action === "sector-filter") {
        state.sectorFilter = el.dataset.filter;
        renderSector();
      }
      if (action === "ticker-filter") {
        state.tickerFilter = el.dataset.filter;
        renderTickers();
      }
      if (action === "ticker-lens") {
        state.tickerLens = el.dataset.lens;
        state.tickerSort = "activeScore";
        renderTickers();
      }
      if (action === "ticker") {
        openTicker(el.dataset.ticker);
      }
      if (action === "close-drawer") {
        closeDrawer();
      }
      if (action === "setup-refresh") {
        await refreshWorkbenchState();
        if (state.setupAvailable) await searchSetupCandidates();
      }
      if (action === "openai-save-key") {
        await saveOpenAiSessionKey();
      }
      if (action === "openai-forget-key") {
        await forgetOpenAiSessionKey();
      }
      if (action === "intake-parse") {
        await parseTickerIntake();
      }
      if (action === "intake-context") {
        await fetchTickerContext(false);
      }
      if (action === "intake-classify") {
        await classifyTickerIntake();
      }
      if (action === "intake-add") {
        await addApprovedTickerIntake();
      }
      if (action === "setup-save-start") {
        const value = document.getElementById("setup-start-date")?.value;
        await mutateSetup("/api/config/start-date", { startDate: value });
      }
      if (action === "setup-search") {
        await searchSetupCandidates();
      }
      if (action === "setup-add") {
        await mutateSetup(`/api/categories/${encodeURIComponent(state.setupCategory)}/add`, { ticker: el.dataset.ticker });
      }
      if (action === "setup-remove") {
        await mutateSetup(`/api/categories/${encodeURIComponent(state.setupCategory)}/remove`, { ticker: el.dataset.ticker });
      }
      if (action === "toggle-refresh") {
        state[el.dataset.key] = !state[el.dataset.key];
        renderSetup();
      }
      if (action === "setup-run") {
        await startWorkbenchRun();
      }
      if (action === "portfolio-review-toggle-refresh") {
        state.portfolioReviewRefreshData = !state.portfolioReviewRefreshData;
        renderPortfolioReview();
      }
      if (action === "portfolio-review-run") {
        await runPortfolioReview();
      }
      if (action === "portfolio-import-csv") {
        await importPortfolioCsv();
      }
    });

    window.addEventListener("resize", () => {
      if (state.view === "overview") renderOverview();
      if (state.view === "compare") renderCompare();
      if (state.view === "sector") renderSector();
      if (state.view === "portfolio-review") renderPortfolioReview();
      if (state.view === "setup") renderSetup();
      if (state.openTicker) openTicker(state.openTicker);
    });

    setupRunStrip();
    render();
    refreshWorkbenchState(true);
    refreshPortfolioReview(true);
  </script>
</body>
</html>
"""


def main() -> None:
    data = enhance_data(build_data())
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    OUTPUT.write_text(html)
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
