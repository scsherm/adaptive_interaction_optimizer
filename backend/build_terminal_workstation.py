#!/usr/bin/env python3
from __future__ import annotations

import json

from build_analyst_workstation import HTML_TEMPLATE, enhance_data
from build_market_dashboard import ROOT, build_data


OUTPUT = ROOT / "market-basket-analyst-workstation-terminal.html"


TERMINAL_STYLE = r"""
    :root {
      --bg: #07090b;
      --panel: #101519;
      --panel-soft: #0b0f12;
      --ink: #ecf4ee;
      --muted: #98a39d;
      --faint: #68736d;
      --line: #243038;
      --line-strong: #39505a;
      --green: #00d084;
      --green-soft: rgba(0, 208, 132, .13);
      --teal: #27d7de;
      --teal-soft: rgba(39, 215, 222, .14);
      --red: #ff5d6c;
      --red-soft: rgba(255, 93, 108, .14);
      --amber: #ffb64d;
      --amber-soft: rgba(255, 182, 77, .14);
      --violet: #b594ff;
      --violet-soft: rgba(181, 148, 255, .14);
      --blue: #62a8ff;
      --blue-soft: rgba(98, 168, 255, .14);
      --shadow: 0 22px 70px rgba(0, 0, 0, .38);
      color-scheme: dark;
    }

    html {
      background: var(--bg);
    }

    body {
      min-height: 100vh;
      color: var(--ink);
      background:
        linear-gradient(180deg, rgba(0, 208, 132, .08), transparent 210px),
        linear-gradient(90deg, rgba(39, 215, 222, .05), transparent 36%, rgba(255, 182, 77, .04) 70%, transparent),
        repeating-linear-gradient(0deg, rgba(255,255,255,.025), rgba(255,255,255,.025) 1px, transparent 1px, transparent 34px),
        repeating-linear-gradient(90deg, rgba(255,255,255,.018), rgba(255,255,255,.018) 1px, transparent 1px, transparent 56px),
        var(--bg);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    button,
    input,
    select,
    textarea {
      color: var(--ink);
    }

    .shell {
      max-width: 1680px;
      padding: 12px 18px 18px;
    }

    .topbar {
      align-items: center;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(16, 21, 25, .96), rgba(7, 9, 11, .94)),
        var(--panel);
      box-shadow: var(--shadow);
    }

    .brand {
      gap: 12px;
    }

    .mark {
      width: 44px;
      height: 44px;
      border-radius: 6px;
      border-color: rgba(0, 208, 132, .45);
      background:
        linear-gradient(90deg, transparent 0 9px, rgba(255,255,255,.12) 9px 10px, transparent 10px 19px, rgba(255,255,255,.12) 19px 20px, transparent 20px),
        linear-gradient(180deg, transparent 0 9px, rgba(255,255,255,.12) 9px 10px, transparent 10px 19px, rgba(255,255,255,.12) 19px 20px, transparent 20px),
        linear-gradient(135deg, rgba(0,208,132,.9), rgba(39,215,222,.8) 46%, rgba(255,182,77,.9));
      box-shadow:
        inset 0 0 0 5px rgba(7, 9, 11, .7),
        0 0 28px rgba(0, 208, 132, .26);
    }

    h1 {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: clamp(22px, 2.25vw, 34px);
      font-weight: 820;
      text-transform: uppercase;
    }

    h2 {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 16px;
      font-weight: 780;
      text-transform: uppercase;
    }

    h3,
    .tile-label,
    th {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .subtle,
    .why,
    .footnote {
      color: var(--muted);
    }

    .run-strip {
      gap: 7px;
      min-width: min(540px, 42vw);
    }

    .run-tile,
    .stat,
    .quality-card,
    .rank-card,
    .candidate-card,
    .mrr-dist-stat,
    .mrr-status,
    .mrr-toggle,
    .refresh-options,
    .intake-status {
      background:
        linear-gradient(180deg, rgba(255,255,255,.045), rgba(255,255,255,.012)),
        var(--panel-soft);
      border-color: var(--line);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
    }

    .run-tile {
      position: relative;
      min-height: 54px;
      overflow: hidden;
    }

    .run-tile::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 3px;
      background: var(--green);
      box-shadow: 0 0 18px rgba(0, 208, 132, .58);
    }

    .tile-label {
      color: var(--faint);
      letter-spacing: .08em;
    }

    .tile-value,
    .stat .value,
    .mrr-dist-stat .value,
    .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-variant-numeric: tabular-nums;
    }

    .nav {
      top: 8px;
      border-color: rgba(0, 208, 132, .26);
      background:
        linear-gradient(180deg, rgba(16, 21, 25, .94), rgba(9, 12, 14, .9));
      box-shadow: 0 12px 36px rgba(0, 0, 0, .32);
    }

    .nav button,
    .seg button,
    .chip,
    .small-btn,
    .icon-btn,
    .primary-btn {
      border-color: var(--line);
      background: rgba(12, 16, 19, .88);
      color: var(--muted);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.035);
    }

    .nav button:hover,
    .seg button:hover,
    .chip:hover,
    .small-btn:hover,
    .icon-btn:hover {
      border-color: rgba(39, 215, 222, .55);
      color: var(--ink);
      background: rgba(39, 215, 222, .08);
      transform: translateY(-1px);
    }

    .nav button.active,
    .seg button.active,
    .chip.active,
    .primary-btn {
      color: #04100b;
      background: linear-gradient(180deg, var(--green), #05aa71);
      border-color: rgba(0, 208, 132, .82);
      box-shadow: 0 0 24px rgba(0, 208, 132, .2);
    }

    .seg {
      background: rgba(0,0,0,.18);
      border-color: var(--line);
    }

    .panel {
      border-color: var(--line);
      background:
        linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.012)),
        rgba(16, 21, 25, .94);
      box-shadow: var(--shadow);
    }

    .panel.flat {
      background: rgba(11, 15, 18, .74);
      border-color: var(--line);
    }

    .panel-head {
      padding: 13px 14px 10px;
      border-bottom-color: var(--line);
      background:
        linear-gradient(90deg, rgba(0, 208, 132, .08), transparent 48%, rgba(255, 182, 77, .055));
    }

    .panel-body {
      padding: 14px;
    }

    .overview-grid {
      grid-template-columns: minmax(300px, .78fr) minmax(480px, 1.45fr) minmax(300px, .82fr);
    }

    .chart {
      border-color: var(--line);
      background:
        linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,.008)),
        #080b0d;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.015);
    }

    .grid-line {
      stroke: rgba(152, 163, 157, .18);
    }

    .axis {
      fill: var(--faint);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .label {
      fill: var(--ink);
      paint-order: stroke;
      stroke: rgba(7,9,11,.72);
      stroke-width: 3px;
      stroke-linejoin: round;
    }

    .point {
      stroke: rgba(236, 244, 238, .86);
    }

    .line-path {
      stroke-width: 2.7;
    }

    .rank-card,
    .candidate-card,
    .sector-btn,
    .mrr-toggle {
      color: var(--ink);
      text-align: left;
    }

    .rank-card:hover,
    .candidate-card:hover,
    .sector-btn:hover,
    .mrr-toggle:hover {
      border-color: rgba(0, 208, 132, .44);
      background:
        linear-gradient(90deg, rgba(0, 208, 132, .08), rgba(39, 215, 222, .025)),
        var(--panel-soft);
    }

    .rank-title,
    strong {
      color: var(--ink);
    }

    .score-pill,
    .coverage-badge.good,
    .source-badge.ok,
    .cycle-badge.hot {
      color: var(--green);
      background: rgba(0, 208, 132, .13);
      border: 1px solid rgba(0, 208, 132, .35);
    }

    .score-pill.amber,
    .coverage-badge.warn,
    .cycle-badge.warning {
      color: var(--amber);
      background: rgba(255, 182, 77, .13);
      border-color: rgba(255, 182, 77, .35);
    }

    .score-pill.red,
    .coverage-badge.bad,
    .source-badge.error,
    .cycle-badge.bad {
      color: var(--red);
      background: rgba(255, 93, 108, .13);
      border-color: rgba(255, 93, 108, .35);
    }

    .cycle-badge.cold {
      color: var(--blue);
      background: rgba(98, 168, 255, .13);
      border-color: rgba(98, 168, 255, .35);
    }

    .score-pill.violet {
      color: var(--violet);
      background: rgba(181, 148, 255, .13);
      border-color: rgba(181, 148, 255, .35);
    }

    .pos {
      color: var(--green);
    }

    .neg {
      color: var(--red);
    }

    .neutral {
      color: var(--muted);
    }

    .table-wrap {
      border-color: var(--line);
      background: #080b0d;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.012);
    }

    table {
      color: var(--ink);
    }

    th,
    th:first-child {
      background: #0e1418;
      color: var(--muted);
      border-bottom-color: var(--line-strong);
    }

    td,
    th {
      border-bottom-color: rgba(57, 80, 90, .55);
    }

    td:first-child {
      background: #0b0f12;
    }

    tr:hover td {
      background: rgba(39, 215, 222, .09);
    }

    tr:hover td:first-child {
      background: #111920;
    }

    .ticker-cell {
      color: var(--ink);
    }

    .input,
    select,
    textarea,
    .intake-table input[type="text"] {
      color: var(--ink);
      border-color: var(--line);
      background: #080b0d;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.035);
    }

    .input:focus,
    select:focus,
    textarea:focus,
    .intake-table input[type="text"]:focus {
      outline: 1px solid rgba(39, 215, 222, .72);
      border-color: rgba(39, 215, 222, .72);
    }

    .bar-track,
    .confidence-meter {
      background: #1b2429;
    }

    .bar-fill,
    .confidence-meter span {
      box-shadow: 0 0 12px rgba(0, 208, 132, .22);
    }

    .drawer {
      background: #0b0f12;
      border-left-color: var(--line-strong);
      box-shadow: -26px 0 80px rgba(0,0,0,.56);
    }

    .drawer-head {
      background:
        linear-gradient(90deg, rgba(0, 208, 132, .1), rgba(39, 215, 222, .04)),
        #101519;
      border-bottom-color: var(--line);
    }

    .drawer-body {
      background: #0b0f12;
    }

    .warning {
      color: var(--amber);
      background: rgba(255, 182, 77, .1);
      border-left-color: var(--amber);
    }

    .empty {
      color: var(--muted);
      border-color: var(--line-strong);
      background:
        linear-gradient(135deg, rgba(255,255,255,.035), rgba(255,255,255,.008)),
        var(--panel-soft);
    }

    .run-log {
      color: #d6f7e8;
      border-color: var(--line-strong);
      background:
        linear-gradient(180deg, rgba(0,208,132,.055), transparent),
        #050708;
    }

    .heatmap-reference,
    .legend-chip,
    .path-pill,
    .source-badge,
    .metric-tag,
    .coverage-badge {
      border-color: var(--line);
      background: rgba(8, 11, 13, .72);
      color: var(--muted);
    }

    .heatmap-cell {
      color: #06100d;
      border-color: rgba(236,244,238,.08);
      box-shadow: inset 0 1px 0 rgba(255,255,255,.08);
    }

    .heatmap-label {
      color: var(--muted);
      background: #0d1316;
    }

    .heatmap-row:hover .heatmap-label {
      color: var(--ink);
      background: #111920;
    }

    .mrr-input-panel,
    .mrr-distribution-panel {
      border-color: rgba(39, 215, 222, .3);
      background:
        linear-gradient(135deg, rgba(0,208,132,.09), rgba(16,21,25,.95) 34%, rgba(181,148,255,.07)),
        var(--panel);
      box-shadow: var(--shadow);
    }

    .mrr-status.current {
      background: rgba(0, 208, 132, .1);
      border-color: rgba(0, 208, 132, .35);
    }

    .mrr-status.pending {
      background: rgba(255, 182, 77, .11);
      border-color: rgba(255, 182, 77, .42);
    }

    .mrr-status.calculating {
      background: rgba(98, 168, 255, .11);
      border-color: rgba(98, 168, 255, .42);
    }

    .mrr-status.error {
      background: rgba(255, 93, 108, .11);
      border-color: rgba(255, 93, 108, .42);
    }

    .mrr-toggle.active {
      border-color: rgba(0, 208, 132, .52);
      background:
        linear-gradient(90deg, rgba(0,208,132,.16), rgba(39,215,222,.045)),
        #0b1112;
      box-shadow:
        inset 0 0 0 1px rgba(0,208,132,.17),
        0 0 16px rgba(0,208,132,.08);
    }

    .mrr-toggle.pending {
      border-color: var(--amber);
    }

    .metric-dir {
      color: var(--muted);
      border-color: var(--line);
      background: rgba(255,255,255,.045);
    }

    .metric-availability {
      color: var(--faint);
    }

    .mrr-dist-chart {
      background:
        linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,.008)),
        #080b0d;
    }

    .candidate-workbench {
      gap: 14px;
    }

    .candidate-workbench > .rank-summary {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      padding: 1px;
      border: 1px solid rgba(39, 215, 222, .16);
      border-radius: 9px;
      background:
        linear-gradient(90deg, rgba(0, 208, 132, .055), rgba(39, 215, 222, .018) 45%, rgba(255, 182, 77, .04)),
        rgba(7, 9, 11, .52);
    }

    .candidate-workbench > .rank-summary .stat {
      min-height: 86px;
      border-color: rgba(57, 80, 90, .72);
      background:
        linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.014)),
        rgba(10, 14, 16, .9);
    }

    .candidate-cockpit {
      grid-template-columns: minmax(520px, 1.32fr) minmax(370px, .68fr);
      align-items: start;
    }

    .candidate-cockpit > .mrr-input-panel,
    .candidate-cockpit > .mrr-distribution-panel {
      margin-bottom: 0;
      min-height: 0;
    }

    .candidate-cockpit .mrr-input-panel {
      position: relative;
      overflow: hidden;
    }

    .candidate-cockpit .mrr-input-panel::before,
    .candidate-cockpit .mrr-distribution-panel::before {
      content: "";
      position: absolute;
      inset: 0 0 auto;
      height: 2px;
      background: linear-gradient(90deg, var(--green), var(--teal), transparent);
      opacity: .9;
    }

    .candidate-cockpit .mrr-input-grid {
      display: flex;
      grid-template-columns: none;
      gap: 8px;
      max-height: none;
      overflow-x: auto;
      overflow-y: hidden;
      padding: 2px 2px 8px;
      scrollbar-width: thin;
      align-items: flex-start;
    }

    .candidate-cockpit .mrr-input-group {
      min-width: 178px;
      max-width: 206px;
      max-height: 208px;
      overflow-y: auto;
      padding: 8px;
      border: 1px solid rgba(57, 80, 90, .48);
      border-radius: 8px;
      background: rgba(7, 9, 11, .32);
      scrollbar-width: thin;
    }

    .candidate-cockpit .mrr-input-head h3,
    .candidate-cockpit .mrr-distribution-head h2 {
      font-size: 14px;
      letter-spacing: .06em;
    }

    .candidate-cockpit .mrr-input-head {
      align-items: center;
      flex-wrap: nowrap;
    }

    .candidate-cockpit .mrr-input-head .subtle {
      display: none;
    }

    .candidate-cockpit .mrr-input-head .compare-strip {
      flex: 0 0 auto;
      flex-wrap: nowrap;
    }

    .mrr-active-tape {
      padding-top: 1px;
      flex-wrap: nowrap;
      overflow-x: auto;
      scrollbar-width: thin;
    }

    .mrr-active-tape span {
      color: rgba(236, 244, 238, .82);
      border-color: rgba(39, 215, 222, .22);
      background:
        linear-gradient(180deg, rgba(39, 215, 222, .075), rgba(0, 208, 132, .045)),
        rgba(7, 9, 11, .52);
    }

    .candidate-cockpit .mrr-distribution-panel {
      position: relative;
      align-content: start;
      background:
        radial-gradient(circle at 100% 0%, rgba(181, 148, 255, .16), transparent 36%),
        linear-gradient(135deg, rgba(0,208,132,.08), rgba(16,21,25,.95) 38%, rgba(39,215,222,.06)),
        var(--panel);
    }

    .candidate-cockpit .mrr-distribution-layout {
      grid-template-columns: 1fr;
      gap: 10px;
    }

    .candidate-cockpit .mrr-dist-stats {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .candidate-cockpit .mrr-dist-stat {
      min-height: 64px;
      padding: 9px;
    }

    .candidate-cockpit .mrr-dist-stat .value {
      font-size: 22px;
    }

    .candidate-cockpit .mrr-dist-note {
      padding: 9px 10px;
      border: 1px solid rgba(57, 80, 90, .62);
      border-radius: 8px;
      background: rgba(7, 9, 11, .44);
    }

    .candidate-cockpit .mrr-dist-chart {
      height: 190px;
      min-height: 190px;
    }

    .candidate-cockpit .mrr-status {
      padding: 8px 10px;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: center;
    }

    .candidate-cockpit .mrr-status span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .candidate-cockpit .mrr-receipt,
    .candidate-cockpit .mrr-active-tape {
      gap: 5px;
    }

    .candidate-cockpit .warning {
      padding: 7px 10px;
    }

    .candidate-cockpit .mrr-toggle {
      min-height: 38px;
      padding: 7px 8px;
    }

    .candidate-cockpit .metric-availability {
      display: none;
    }

    .candidate-cockpit .metric-name {
      font-size: 11px;
    }

    .candidate-command-bar {
      top: 78px;
      padding: 10px;
      flex-wrap: nowrap;
      overflow-x: auto;
      scrollbar-width: thin;
      border-color: rgba(0, 208, 132, .28);
      background:
        linear-gradient(90deg, rgba(11, 15, 18, .94), rgba(10, 14, 16, .88)),
        rgba(7, 9, 11, .84);
      box-shadow:
        0 16px 34px rgba(0, 0, 0, .38),
        inset 0 1px 0 rgba(255,255,255,.04);
    }

    .candidate-command-bar .input,
    .candidate-command-bar select {
      min-height: 36px;
      flex: 0 0 auto;
    }

    .candidate-command-bar .chip {
      min-height: 34px;
      flex: 0 0 auto;
    }

    .candidate-table-shell {
      padding: 1px;
      border: 1px solid rgba(57, 80, 90, .5);
      border-radius: 9px;
      background:
        linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,.008)),
        rgba(7, 9, 11, .58);
    }

    .candidate-table-head {
      padding: 10px 11px 0;
    }

    .candidate-table-head h3 {
      color: var(--ink);
    }

    .candidate-table-shell .table-wrap {
      max-height: min(690px, 70vh);
      overflow: auto;
      border-top-left-radius: 0;
      border-top-right-radius: 0;
    }

    .candidate-table-shell th {
      position: sticky;
      top: 0;
      z-index: 4;
      background:
        linear-gradient(180deg, #121a1f, #0c1114);
      box-shadow: 0 1px 0 rgba(57, 80, 90, .9);
    }

    .candidate-table-shell tbody tr:nth-child(even) td {
      background-color: rgba(255,255,255,.012);
    }

    .candidate-table-shell tr:hover td {
      background:
        linear-gradient(90deg, rgba(0, 208, 132, .09), rgba(39, 215, 222, .055));
    }

    .candidate-table-shell tr:hover td:first-child {
      background:
        linear-gradient(90deg, rgba(0, 208, 132, .13), rgba(17, 25, 32, .92));
    }

    .dist-fill {
      fill: rgba(39, 215, 222, .11);
    }

    .dist-curve {
      stroke: var(--teal);
    }

    .dist-band-label {
      fill: var(--green);
    }

    .dist-marker-label {
      fill: var(--muted);
    }

    .sector-list {
      top: 92px;
    }

    .sector-btn {
      background: rgba(12, 16, 19, .88);
      border-color: var(--line);
    }

    .sector-btn.active {
      border-color: rgba(0, 208, 132, .7);
      box-shadow:
        inset 0 0 0 1px rgba(0,208,132,.22),
        0 0 20px rgba(0,208,132,.1);
    }

    .source-badges {
      color: var(--muted);
    }

    .coverage-dot {
      background: #2c363c;
      border-color: rgba(236,244,238,.08);
    }

    .coverage-dot.good {
      background: var(--green);
      box-shadow: 0 0 10px rgba(0, 208, 132, .35);
    }

    ::selection {
      color: #04100b;
      background: var(--green);
    }

    ::-webkit-scrollbar {
      width: 12px;
      height: 12px;
    }

    ::-webkit-scrollbar-track {
      background: #07090b;
    }

    ::-webkit-scrollbar-thumb {
      background: #233039;
      border: 3px solid #07090b;
      border-radius: 999px;
    }

    ::-webkit-scrollbar-thumb:hover {
      background: #36515c;
    }

    @media (max-width: 1180px) {
      .overview-grid,
      .two-col,
      .three-col,
      .quality-grid,
      .setup-grid,
      .rank-summary,
      .mrr-distribution-layout,
      .candidate-workbench > .rank-summary,
      .candidate-cockpit,
      .intake-panel,
      .intake-key-grid {
        grid-template-columns: 1fr;
      }

      .candidate-cockpit .mrr-input-grid,
      .candidate-cockpit .mrr-dist-stats {
        grid-template-columns: none;
      }

      .candidate-cockpit .mrr-input-head,
      .candidate-command-bar {
        flex-wrap: wrap;
      }

      .candidate-cockpit .mrr-status {
        grid-template-columns: 1fr;
      }

      .candidate-cockpit .mrr-status span {
        white-space: normal;
      }

      .run-strip {
        min-width: 0;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .sector-layout {
        grid-template-columns: 1fr;
      }

      .sector-list {
        position: static;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 720px) {
      .shell {
        padding: 12px;
      }

      .topbar {
        align-items: stretch;
      }

      .stat-grid,
      .split-list,
      .sector-list {
        grid-template-columns: 1fr;
      }
    }
"""


def apply_terminal_theme(template: str) -> str:
    if "</style>" not in template:
        raise RuntimeError("Analyst workstation template is missing a style block.")
    html = template.replace("</style>", f"\n{TERMINAL_STYLE}\n  </style>", 1)
    html = html.replace(
        "<title>Market Basket Analyst Workstation</title>",
        '<title>Market Basket Analyst Terminal</title>\n  <link rel="icon" href="data:,">',
        1,
    )
    html = html.replace(
        "<h1>Market Basket Analyst Workstation</h1>",
        "<h1>Market Basket Analyst Terminal</h1>",
        1,
    )
    html = html.replace(
        "Cross-sector rotation, setup quality, positioning, fundamentals, and data confidence.",
        "Dark terminal view for cross-sector rotation, setup quality, positioning, fundamentals, and data confidence.",
        1,
    )
    return html


def main() -> None:
    data = enhance_data(build_data())
    html = apply_terminal_theme(HTML_TEMPLATE).replace("__DATA__", json.dumps(data, separators=(",", ":")))
    OUTPUT.write_text(html)
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
