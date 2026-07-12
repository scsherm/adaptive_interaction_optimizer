#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from build_market_dashboard import BASKET_META, DATA_DIR, ROOT


OUTPUT = ROOT / "market-basket-sentiment-workstation.html"
SENTIMENT_DIR = DATA_DIR / "sentiment"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def as_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "")
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def as_int(row: dict[str, str], key: str) -> int:
    value = row.get(key, "")
    if value == "":
        return 0
    return int(float(value))


def build_payload() -> dict[str, Any]:
    baskets = []
    for row in read_csv(DATA_DIR / "basket_news_sentiment.csv"):
        meta = BASKET_META.get(row["basket"], {})
        baskets.append(
            {
                "rank": as_int(row, "rank"),
                "date": row.get("date", ""),
                "basket": row["basket"],
                "label": row["label"],
                "short": row["short"],
                "color": meta.get("color", row.get("color", "#286fb1")),
                "accent": meta.get("accent", row.get("accent", "#286fb1")),
                "tone": as_float(row, "basket_news_tone_score"),
                "investorTone": as_float(row, "basket_investor_tone_score"),
                "attention": as_float(row, "basket_attention_score"),
                "momentum": as_float(row, "basket_sentiment_momentum"),
                "negativeSpike": as_float(row, "basket_negative_spike_score"),
                "positiveSpike": as_float(row, "basket_positive_spike_score"),
                "sourceDiversity": as_float(row, "source_diversity_score"),
                "coverageConfidence": as_float(row, "coverage_confidence"),
                "demandTailwind": as_float(row, "demand_tailwind_score"),
                "demandRisk": as_float(row, "demand_risk_score"),
                "investorPositive": as_float(row, "investor_positive_score"),
                "investorNegative": as_float(row, "investor_negative_score"),
                "companyPositive": as_float(row, "company_positive_score"),
                "companyRisk": as_float(row, "company_risk_score"),
                "llmRelevantArticles": as_int(row, "llm_relevant_articles"),
                "llmTotalArticles": as_int(row, "llm_total_articles"),
                "llmAverageConfidence": as_float(row, "llm_average_confidence"),
                "scoringMethod": row.get("scoring_method", ""),
                "marketContext": as_float(row, "market_context_score"),
                "state": row["basket_sentiment_state"],
                "mentionVolume": as_float(row, "mention_volume"),
                "mentionVolumeZ": as_float(row, "mention_volume_zscore"),
                "primarySignal": row.get("primary_signal", ""),
                "riskSignal": row.get("risk_signal", ""),
            }
        )

    tickers = []
    for row in read_csv(DATA_DIR / "ticker_news_sentiment.csv"):
        tickers.append(
            {
                "basket": row["basket"],
                "ticker": row["ticker"],
                "label": row["label"],
                "companyName": row["company_name"],
                "tone": as_float(row, "news_tone_score"),
                "investorTone": as_float(row, "investor_tone_score"),
                "attention": as_float(row, "attention_score"),
                "momentum7d": as_float(row, "sentiment_momentum_7d"),
                "momentum30d": as_float(row, "sentiment_momentum_30d"),
                "negativeSpike": as_float(row, "negative_news_spike_score"),
                "positiveSpike": as_float(row, "positive_news_spike_score"),
                "coverageConfidence": as_float(row, "coverage_confidence"),
                "demandTailwind": as_float(row, "demand_tailwind_score"),
                "demandRisk": as_float(row, "demand_risk_score"),
                "investorPositive": as_float(row, "investor_positive_score"),
                "investorNegative": as_float(row, "investor_negative_score"),
                "companyPositive": as_float(row, "company_positive_score"),
                "companyRisk": as_float(row, "company_risk_score"),
                "llmRelevantArticles": as_int(row, "llm_relevant_articles"),
                "llmTotalArticles": as_int(row, "llm_total_articles"),
                "llmAverageConfidence": as_float(row, "llm_average_confidence"),
                "scoringMethod": row.get("scoring_method", ""),
                "marketContext": as_float(row, "market_context_score"),
                "state": row["sentiment_state"],
                "mentionVolume": as_float(row, "mention_volume"),
                "topPositiveHeadline": row.get("top_positive_headline", ""),
                "topPositiveUrl": row.get("top_positive_url", ""),
                "topNegativeHeadline": row.get("top_negative_headline", ""),
                "topNegativeUrl": row.get("top_negative_url", ""),
            }
        )

    events = []
    for row in read_csv(DATA_DIR / "sentiment_events.csv"):
        events.append(
            {
                "basket": row["basket"],
                "ticker": row["ticker"],
                "queryType": row["query_type"],
                "eventType": row["event_type"],
                "eventScore": as_float(row, "event_score"),
                "publishedAt": row["published_at"],
                "source": row["source"],
                "domain": row["domain"],
                "title": row["title"],
                "url": row["url"],
                "toneScore": as_float(row, "tone_score"),
                "entityConfidence": as_float(row, "entity_confidence"),
                "marketRelevant": row.get("is_market_relevant", ""),
            }
        )

    articles = []
    for row in sorted(read_csv(SENTIMENT_DIR / "news_raw.csv"), key=lambda item: item.get("published_at", ""), reverse=True)[:1200]:
        articles.append(
            {
                "basket": row["basket"],
                "ticker": row["ticker"],
                "companyName": row.get("company_name", ""),
                "queryType": row["query_type"],
                "query": row["query"],
                "publishedAt": row["published_at"],
                "source": row["source"],
                "domain": row["domain"],
                "title": row["title"],
                "url": row["url"],
                "language": row["language"],
                "toneScore": as_float(row, "tone_score"),
                "providerSentimentScore": as_float(row, "provider_sentiment_score"),
                "providerSentimentLabel": row.get("provider_sentiment_label", ""),
                "tickerSentimentScore": as_float(row, "ticker_sentiment_score"),
                "tickerSentimentLabel": row.get("ticker_sentiment_label", ""),
                "tickerRelevanceScore": as_float(row, "ticker_relevance_score"),
            }
        )

    timeline = []
    for row in read_csv(SENTIMENT_DIR / "news_timeline_raw.csv"):
        timeline.append(
            {
                "basket": row["basket"],
                "ticker": row["ticker"],
                "queryType": row["query_type"],
                "query": row["query"],
                "date": row["date"],
                "metric": row["metric"],
                "value": as_float(row, "value"),
            }
        )

    return {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": read_json(DATA_DIR / "sentiment_summary.json"),
        "qa": read_json(DATA_DIR / "sentiment_qa_report.json"),
        "baskets": baskets,
        "tickers": tickers,
        "events": events,
        "articles": articles,
        "timeline": timeline,
        "llm": read_csv(SENTIMENT_DIR / "news_llm_analysis.csv"),
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Basket Sentiment Workstation</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f5ef;
      --ink: #171916;
      --muted: #626a60;
      --faint: #858e7c;
      --panel: #ffffff;
      --soft: #fbfbf7;
      --line: #d9dfd2;
      --line-strong: #b8c2b1;
      --good: #08704f;
      --bad: #b23a3a;
      --amber: #a76614;
      --blue: #286fb1;
      --violet: #684da3;
      --shadow: 0 18px 44px rgb(25 27 24 / .08);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-variant-numeric: tabular-nums;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(180deg, rgb(255 255 255 / .82), rgb(255 255 255 / 0) 340px),
        repeating-linear-gradient(90deg, rgb(25 27 24 / .025), rgb(25 27 24 / .025) 1px, transparent 1px, transparent 86px),
        var(--bg);
    }
    button, select, input { font: inherit; }
    button { cursor: pointer; }
    .shell { max-width: 1560px; margin: 0 auto; padding: 24px; }
    .topbar { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; margin-bottom: 16px; }
    .brand { display: flex; gap: 14px; align-items: center; min-width: 0; }
    .mark {
      width: 46px; height: 46px; border-radius: 8px; border: 1px solid var(--line-strong);
      background: linear-gradient(135deg, var(--blue) 0 32%, var(--good) 32% 64%, var(--amber) 64% 100%);
      box-shadow: inset 0 0 0 4px rgb(255 255 255 / .68);
      flex: 0 0 auto;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(26px, 3vw, 42px); line-height: 1; letter-spacing: 0; }
    h2 { font-size: 18px; line-height: 1.2; }
    h3 { font-size: 13px; line-height: 1.25; }
    .subtle { color: var(--muted); font-size: 13px; line-height: 1.45; }
    .top-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .btn, .chip {
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 8px;
      padding: 8px 11px;
      text-decoration: none;
      font-size: 12px;
      font-weight: 720;
      display: inline-flex;
      align-items: center;
      gap: 7px;
    }
    .btn.primary, .chip.active { background: var(--ink); border-color: var(--ink); color: #fff; }
    .status-strip { display: grid; grid-template-columns: repeat(5, minmax(140px, 1fr)); gap: 9px; margin-bottom: 14px; }
    .tile, .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgb(255 255 255 / .9);
      box-shadow: var(--shadow);
    }
    .tile { padding: 12px; min-height: 86px; }
    .tile .label { color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .02em; }
    .tile .value { font-size: 25px; font-weight: 820; margin-top: 8px; }
    .tile .note { color: var(--muted); font-size: 12px; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .toolbar { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; }
    .select-wrap { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    select, input {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 8px 10px;
      min-height: 36px;
    }
    .grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(360px, .9fr); gap: 14px; align-items: start; }
    .panel { padding: 14px; min-width: 0; }
    .panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
    .chart { width: 100%; min-height: 360px; border: 1px solid var(--line); border-radius: 8px; background: var(--soft); overflow: hidden; }
    .table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
    th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .02em; background: rgb(251 251 247 / .8); position: sticky; top: 0; z-index: 1; }
    td.num { text-align: right; white-space: nowrap; }
    .scroll { max-height: 520px; overflow: auto; border: 1px solid var(--line); border-radius: 8px; }
    .state {
      display: inline-flex; align-items: center; gap: 6px; padding: 5px 8px; border-radius: 999px;
      border: 1px solid var(--line); background: var(--soft); font-size: 11px; font-weight: 780; white-space: nowrap;
    }
    .state.good { color: var(--good); background: #dfeee7; border-color: #bdd9ca; }
    .state.bad { color: var(--bad); background: #f3e1df; border-color: #e0bfba; }
    .state.warn { color: var(--amber); background: #f3ead9; border-color: #dfcba7; }
    .state.info { color: var(--blue); background: #e1eaf4; border-color: #bfd1e1; }
    .bar {
      height: 8px; border-radius: 999px; background: #e6eadf; overflow: hidden; min-width: 82px;
    }
    .bar span { display: block; height: 100%; background: var(--blue); border-radius: inherit; }
    .ticker-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 9px; }
    .ticker-card { border: 1px solid var(--line); border-radius: 8px; background: var(--soft); padding: 11px; min-height: 142px; }
    .ticker-top { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
    .ticker-symbol { font-weight: 850; }
    .metrics-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; margin-top: 9px; }
    .mini { border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 7px; }
    .mini b { display: block; font-size: 14px; }
    .mini span { color: var(--muted); font-size: 10px; text-transform: uppercase; font-weight: 800; }
    .article-list { display: grid; gap: 8px; }
    .article { border: 1px solid var(--line); border-radius: 8px; background: var(--soft); padding: 11px; }
    .article a { color: var(--ink); font-weight: 780; text-decoration: none; }
    .article a:hover { color: var(--blue); text-decoration: underline; }
    .meta { display: flex; gap: 8px; flex-wrap: wrap; color: var(--muted); font-size: 11px; margin-top: 7px; }
    .hidden { display: none; }
    .empty { color: var(--muted); font-size: 13px; padding: 18px; border: 1px dashed var(--line-strong); border-radius: 8px; background: var(--soft); }
    @media (max-width: 980px) {
      .shell { padding: 14px; }
      .topbar, .grid { grid-template-columns: 1fr; display: grid; }
      .status-strip { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
      .top-actions { justify-content: flex-start; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="topbar">
      <div class="brand">
        <div class="mark" aria-hidden="true"></div>
        <div>
          <h1>Market Basket Sentiment Workstation</h1>
          <p class="subtle" id="subtitle"></p>
        </div>
      </div>
      <div class="top-actions">
        <a class="btn" href="market-basket-analyst-workstation.html">Analyst</a>
        <a class="btn" href="market-basket-analyst-workstation-rotation.html">Rotation</a>
        <a class="btn primary" href="market-basket-sentiment-workstation.html">Sentiment</a>
      </div>
    </div>

    <div class="status-strip" id="statusStrip"></div>

    <div class="toolbar">
      <div class="tabs" id="tabs"></div>
      <div class="select-wrap">
        <select id="basketSelect" aria-label="Basket"></select>
        <input id="articleSearch" type="search" placeholder="Headline filter">
      </div>
    </div>

    <section class="grid">
      <div class="panel">
        <div class="panel-head">
          <div>
            <h2 id="mainTitle">Sentiment Map</h2>
            <p class="subtle" id="mainNote"></p>
          </div>
          <button class="btn" id="resetBasket">All baskets</button>
        </div>
        <div id="mainView"></div>
      </div>
      <div class="panel">
        <div class="panel-head">
          <div>
            <h2 id="sideTitle">Narrative States</h2>
            <p class="subtle" id="sideNote"></p>
          </div>
        </div>
        <div id="sideView"></div>
      </div>
    </section>
  </div>

  <script type="application/json" id="sentiment-data">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById('sentiment-data').textContent);
    const state = {
      tab: 'map',
      basket: '',
      search: ''
    };
    const tabs = [
      ['map', 'Sentiment Map'],
      ['timeline', 'Tone Timeline'],
      ['spikes', 'Spike Board'],
      ['setups', 'Setups'],
      ['articles', 'Article Drilldown']
    ];

    const fmt = (value, digits = 0) => value === null || value === undefined || Number.isNaN(value) ? 'n/a' : Number(value).toFixed(digits);
    const esc = (text) => String(text ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    const stateClass = (label) => {
      if (/Positive|Contrarian/.test(label)) return 'good';
      if (/Negative|Breakdown|Fear/.test(label)) return 'bad';
      if (/Crowded|Tailwind|Spike/.test(label)) return 'warn';
      return 'info';
    };
    const scoreBar = (value, color = 'var(--blue)') => `<div class="bar"><span style="width:${Math.max(0, Math.min(100, value || 0))}%; background:${color}"></span></div>`;
    const activeBaskets = () => state.basket ? DATA.baskets.filter(row => row.basket === state.basket) : DATA.baskets;
    const activeTickers = () => state.basket ? DATA.tickers.filter(row => row.basket === state.basket) : DATA.tickers;
    const activeArticles = () => {
      const term = state.search.toLowerCase();
      return DATA.articles.filter(row => (!state.basket || row.basket === state.basket) && (!term || `${row.title} ${row.ticker} ${row.query}`.toLowerCase().includes(term)));
    };

    function renderChrome() {
      const summary = DATA.summary || {};
      const qa = DATA.qa || {};
      document.getElementById('subtitle').textContent = `Generated ${DATA.generatedAt || ''} | Provider ${summary.provider || 'GDELT_DOC'} | QA ${qa.status || 'not run'}`;
      document.getElementById('statusStrip').innerHTML = [
        ['Raw Articles', summary.raw_article_rows ?? DATA.articles.length, `${DATA.articles.length} embedded in workstation`],
        ['LLM Rows', summary.llm_analysis_rows ?? DATA.llm.length, 'structured narrative classifications'],
        ['Timeline Rows', summary.timeline_rows ?? DATA.timeline.length, 'tone and attention history'],
        ['Coverage', avg(DATA.baskets.map(row => row.coverageConfidence)), 'average confidence'],
        ['Latest News', summary.latest_news_date || '', 'raw data recency']
      ].map(([label, value, note]) => `
        <div class="tile">
          <div class="label">${esc(label)}</div>
          <div class="value">${typeof value === 'number' ? fmt(value, value % 1 ? 1 : 0) : esc(value)}</div>
          <div class="note">${esc(note)}</div>
        </div>`).join('');
      document.getElementById('tabs').innerHTML = tabs.map(([id, label]) => `<button class="chip ${state.tab === id ? 'active' : ''}" data-tab="${id}">${label}</button>`).join('');
      document.querySelectorAll('[data-tab]').forEach(btn => btn.addEventListener('click', () => { state.tab = btn.dataset.tab; render(); }));
      const select = document.getElementById('basketSelect');
      select.innerHTML = `<option value="">All baskets</option>` + DATA.baskets.map(row => `<option value="${esc(row.basket)}">${esc(row.label)}</option>`).join('');
      select.value = state.basket;
      select.onchange = () => { state.basket = select.value; render(); };
      document.getElementById('resetBasket').onclick = () => { state.basket = ''; render(); };
      const search = document.getElementById('articleSearch');
      search.value = state.search;
      search.oninput = () => { state.search = search.value; if (state.tab === 'articles') renderViews(); };
    }

    function avg(values) {
      const valid = values.filter(value => Number.isFinite(value));
      if (!valid.length) return null;
      return valid.reduce((sum, value) => sum + value, 0) / valid.length;
    }

    function renderViews() {
      if (state.tab === 'map') return renderMap();
      if (state.tab === 'timeline') return renderTimeline();
      if (state.tab === 'spikes') return renderSpikes();
      if (state.tab === 'setups') return renderSetups();
      return renderArticles();
    }

    function renderMap() {
      document.getElementById('mainTitle').textContent = 'Sentiment Map';
      document.getElementById('mainNote').textContent = 'Tone vs attention, sized by coverage confidence.';
      const rows = DATA.baskets;
      const width = 900, height = 430, pad = 48;
      const x = value => pad + (Math.max(0, Math.min(100, value || 0)) / 100) * (width - pad * 2);
      const y = value => height - pad - (Math.max(0, Math.min(100, value || 0)) / 100) * (height - pad * 2);
      document.getElementById('mainView').innerHTML = `
        <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Sentiment map">
          <rect x="0" y="0" width="${width}" height="${height}" fill="#fbfbf7"></rect>
          <line x1="${pad}" x2="${width - pad}" y1="${y(50)}" y2="${y(50)}" stroke="#d9dfd2"></line>
          <line x1="${x(50)}" x2="${x(50)}" y1="${pad}" y2="${height - pad}" stroke="#d9dfd2"></line>
          <text x="${pad}" y="${height - 13}" fill="#626a60" font-size="12">Lower attention</text>
          <text x="${width - 142}" y="${height - 13}" fill="#626a60" font-size="12">Higher attention</text>
          <text x="12" y="${pad}" fill="#626a60" font-size="12">Positive tone</text>
          <text x="12" y="${height - pad}" fill="#626a60" font-size="12">Negative tone</text>
          ${rows.map(row => {
            const active = !state.basket || state.basket === row.basket;
            const radius = 10 + Math.max(0, Math.min(100, row.coverageConfidence || 0)) / 7;
            return `<g style="cursor:pointer; opacity:${active ? 1 : .24}" data-basket-dot="${esc(row.basket)}">
              <circle cx="${x(row.attention)}" cy="${y(row.tone)}" r="${radius}" fill="${esc(row.color)}" stroke="#171916" stroke-width="1.2"></circle>
              <text x="${x(row.attention) + radius + 5}" y="${y(row.tone) + 4}" font-size="12" font-weight="800" fill="#171916">${esc(row.short)}</text>
            </g>`;
          }).join('')}
        </svg>`;
      document.querySelectorAll('[data-basket-dot]').forEach(node => node.addEventListener('click', () => { state.basket = node.dataset.basketDot; render(); }));
      renderStateTable();
    }

    function renderStateTable() {
      const rows = activeBaskets();
      document.getElementById('sideTitle').textContent = state.basket ? rows[0]?.label || 'Basket' : 'Narrative States';
      document.getElementById('sideNote').textContent = 'Basket scores are 0-100; 50 is neutral for tone and momentum.';
      document.getElementById('sideView').innerHTML = `
        <div class="scroll">
          <table class="table">
            <thead><tr><th>Basket</th><th>State</th><th class="num">Tone</th><th class="num">Attention</th><th>Method</th><th>Signal</th></tr></thead>
            <tbody>${rows.map(row => `
              <tr>
                <td><b>${esc(row.label)}</b><div class="subtle">${esc(row.short)}</div></td>
                <td><span class="state ${stateClass(row.state)}">${esc(row.state)}</span></td>
                <td class="num">${fmt(row.tone)}</td>
                <td class="num">${fmt(row.attention)}</td>
                <td><span class="state info">${esc(row.scoringMethod || 'n/a')}</span><div class="subtle">${row.llmTotalArticles ? `${row.llmRelevantArticles}/${row.llmTotalArticles} LLM` : ''}</div></td>
                <td>${esc(row.primarySignal)}<div class="subtle">${esc(row.riskSignal)}</div></td>
              </tr>`).join('')}</tbody>
          </table>
        </div>`;
    }

    function renderTimeline() {
      const basket = state.basket || DATA.baskets[0]?.basket || '';
      const label = DATA.baskets.find(row => row.basket === basket)?.label || 'Basket';
      document.getElementById('mainTitle').textContent = `${label} Tone Timeline`;
      document.getElementById('mainNote').textContent = 'Average tone and raw attention from fetched timeline rows.';
      const grouped = {};
      DATA.timeline.filter(row => row.basket === basket).forEach(row => {
        const day = (row.date || '').slice(0, 10);
        if (!day) return;
        grouped[day] ||= { date: day, tone: [], volume: 0 };
        if (row.metric === 'tone' && Number.isFinite(row.value)) grouped[day].tone.push(row.value);
        if (row.metric === 'volume_raw' && Number.isFinite(row.value)) grouped[day].volume += row.value;
      });
      const points = Object.values(grouped).sort((a, b) => a.date.localeCompare(b.date)).map(row => ({...row, toneValue: avg(row.tone)})).slice(-90);
      if (!points.length) {
        document.getElementById('mainView').innerHTML = '<div class="empty">No timeline rows are available for this basket yet.</div>';
      } else {
        const width = 900, height = 430, pad = 48;
        const maxVol = Math.max(1, ...points.map(row => row.volume));
        const x = index => pad + (index / Math.max(1, points.length - 1)) * (width - pad * 2);
        const yTone = value => height - pad - ((Math.max(-10, Math.min(10, value || 0)) + 10) / 20) * (height - pad * 2);
        const yVol = value => height - pad - (value / maxVol) * (height - pad * 2) * .45;
        const tonePath = points.map((row, idx) => `${idx ? 'L' : 'M'} ${x(idx)} ${yTone(row.toneValue || 0)}`).join(' ');
        const volPath = points.map((row, idx) => `${idx ? 'L' : 'M'} ${x(idx)} ${yVol(row.volume)}`).join(' ');
        document.getElementById('mainView').innerHTML = `
          <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Tone timeline">
            <rect width="${width}" height="${height}" fill="#fbfbf7"></rect>
            <line x1="${pad}" x2="${width - pad}" y1="${yTone(0)}" y2="${yTone(0)}" stroke="#d9dfd2"></line>
            <path d="${volPath}" fill="none" stroke="#a76614" stroke-width="3" opacity=".55"></path>
            <path d="${tonePath}" fill="none" stroke="#286fb1" stroke-width="3"></path>
            ${points.filter((_, idx) => idx % Math.ceil(points.length / 8) === 0).map((row, idx) => `<text x="${x(idx * Math.ceil(points.length / 8))}" y="${height - 14}" font-size="11" fill="#626a60">${esc(row.date.slice(5))}</text>`).join('')}
            <text x="${pad}" y="${pad - 18}" fill="#286fb1" font-size="12" font-weight="800">Tone</text>
            <text x="${pad + 56}" y="${pad - 18}" fill="#a76614" font-size="12" font-weight="800">Attention</text>
          </svg>`;
      }
      renderTickerPanel(basket);
    }

    function renderTickerPanel(basket) {
      const rows = DATA.tickers.filter(row => row.basket === basket).sort((a, b) => (b.attention || 0) - (a.attention || 0));
      document.getElementById('sideTitle').textContent = 'Ticker Sentiment';
      document.getElementById('sideNote').textContent = 'Company-level media tone, attention, and coverage confidence.';
      document.getElementById('sideView').innerHTML = rows.length ? `<div class="ticker-grid">${rows.map(row => `
        <div class="ticker-card">
          <div class="ticker-top">
            <div><div class="ticker-symbol">${esc(row.ticker)}</div><div class="subtle">${esc(row.companyName)}</div></div>
            <span class="state ${stateClass(row.state)}">${esc(row.state)}</span>
          </div>
          <div class="metrics-row">
            <div class="mini"><b>${fmt(row.tone)}</b><span>Tone</span></div>
            <div class="mini"><b>${fmt(row.attention)}</b><span>Attention</span></div>
            <div class="mini"><b>${fmt(row.coverageConfidence)}</b><span>Coverage</span></div>
          </div>
          <div class="metrics-row">
            <div class="mini"><b>${fmt(row.demandTailwind)}</b><span>Demand +</span></div>
            <div class="mini"><b>${fmt(row.demandRisk)}</b><span>Demand -</span></div>
            <div class="mini"><b>${esc(row.scoringMethod || 'n/a')}</b><span>Method</span></div>
          </div>
          <p class="subtle" style="margin-top:9px">${esc(row.topPositiveHeadline || row.topNegativeHeadline || 'No headline drilldown yet')}</p>
        </div>`).join('')}</div>` : '<div class="empty">No ticker sentiment rows for this basket yet.</div>';
    }

    function renderSpikes() {
      document.getElementById('mainTitle').textContent = 'Attention Spike Board';
      document.getElementById('mainNote').textContent = 'Coverage surges, negative spikes, and positive headline pressure.';
      const rows = activeBaskets().slice().sort((a, b) => (b.attention || 0) - (a.attention || 0));
      document.getElementById('mainView').innerHTML = `
        <div class="scroll">
          <table class="table">
            <thead><tr><th>Basket</th><th class="num">Attention</th><th class="num">Z</th><th>Demand Risk</th><th>Demand Tailwind</th><th>State</th></tr></thead>
            <tbody>${rows.map(row => `
              <tr>
                <td><b>${esc(row.label)}</b><div class="subtle">${esc(row.primarySignal)}</div></td>
                <td class="num">${fmt(row.attention)}</td>
                <td class="num">${fmt(row.mentionVolumeZ, 2)}</td>
                <td>${scoreBar(row.demandRisk ?? row.negativeSpike, 'var(--bad)')}</td>
                <td>${scoreBar(row.demandTailwind ?? row.positiveSpike, 'var(--good)')}</td>
                <td><span class="state ${stateClass(row.state)}">${esc(row.state)}</span></td>
              </tr>`).join('')}</tbody>
          </table>
        </div>`;
      renderStateTable();
    }

    function renderSetups() {
      document.getElementById('mainTitle').textContent = 'Contrarian And Crowding Setups';
      document.getElementById('mainNote').textContent = 'Sentiment states that require market context after news scoring.';
      const setupRows = activeBaskets().filter(row => /Contrarian|Crowded|Breakdown|Tailwind/.test(row.state));
      document.getElementById('mainView').innerHTML = setupRows.length ? `
        <div class="scroll">
          <table class="table">
            <thead><tr><th>Basket</th><th>State</th><th class="num">Tone</th><th class="num">Attention</th><th class="num">Market</th><th>Read</th></tr></thead>
            <tbody>${setupRows.map(row => `
              <tr>
                <td><b>${esc(row.label)}</b></td>
                <td><span class="state ${stateClass(row.state)}">${esc(row.state)}</span></td>
                <td class="num">${fmt(row.tone)}</td>
                <td class="num">${fmt(row.attention)}</td>
                <td class="num">${fmt(row.marketContext)}</td>
                <td>${esc(row.primarySignal)}<div class="subtle">${esc(row.riskSignal)}</div></td>
              </tr>`).join('')}</tbody>
          </table>
        </div>` : '<div class="empty">No contrarian or crowding states are active in the current filter.</div>';
      const basket = state.basket || DATA.baskets[0]?.basket || '';
      renderTickerPanel(basket);
    }

    function renderArticles() {
      document.getElementById('mainTitle').textContent = 'Article Drilldown';
      document.getElementById('mainNote').textContent = 'Raw cached articles and scored events, filtered by basket and headline text.';
      const articles = activeArticles().slice(0, 160);
      document.getElementById('mainView').innerHTML = articles.length ? `
        <div class="article-list">${articles.map(row => `
          <article class="article">
            <a href="${esc(row.url)}" target="_blank" rel="noreferrer">${esc(row.title || 'Untitled article')}</a>
            <div class="meta">
              <span>${esc(row.publishedAt ? row.publishedAt.slice(0, 10) : '')}</span>
              <span>${esc(row.domain || row.source)}</span>
              <span>${esc(row.ticker || row.basket)}</span>
              <span>${esc(row.queryType)}</span>
              <span>${row.tickerSentimentLabel ? esc(row.tickerSentimentLabel) : ''}</span>
              <span>${row.toneScore === null ? 'tone n/a' : `tone ${fmt(row.toneScore, 1)}`}</span>
            </div>
          </article>`).join('')}</div>` : '<div class="empty">No article rows match the current filter.</div>';
      const events = DATA.events.filter(row => !state.basket || row.basket === state.basket).slice(0, 80);
      document.getElementById('sideTitle').textContent = 'Scored Events';
      document.getElementById('sideNote').textContent = 'Top positive and negative headlines selected for audit.';
      document.getElementById('sideView').innerHTML = events.length ? `<div class="article-list">${events.map(row => `
        <article class="article">
          <span class="state ${stateClass(row.eventType)}">${esc(row.eventType)}</span>
          <p style="margin-top:8px"><a href="${esc(row.url)}" target="_blank" rel="noreferrer">${esc(row.title)}</a></p>
          <div class="meta"><span>${esc(row.ticker || row.basket)}</span><span>${esc(row.domain)}</span><span>score ${fmt(row.eventScore)}</span></div>
        </article>`).join('')}</div>` : '<div class="empty">No scored events available yet.</div>';
    }

    function render() {
      renderChrome();
      renderViews();
    }
    render();
  </script>
</body>
</html>
"""


def main() -> None:
    payload = build_payload()
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    OUTPUT.write_text(HTML_TEMPLATE.replace("__DATA__", data))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
