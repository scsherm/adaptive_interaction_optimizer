# Adaptive Interaction Optimizer

Interaction-focused system demonstrated through a market-basket research workstation.

```bash
npm install
npm run setup
npm run dev
```

`npm run dev` starts the bundled analysis workstation at `http://localhost:3000/workstation`.
`npm run check` runs syntax checks plus the universe/datastore test suite.

## The basket universe

`backend/config/universe.yaml` is the single source of truth for baskets. One entry
carries everything the system knows about a basket:

```yaml
- id: cybersecurity
  label: Cybersecurity
  short: Cyber
  color: '#6bb7ff'
  accent: oklch(74% 0.14 245)
  path: [Technology, Security Software, Cybersecurity]   # taxonomy placement
  description: Endpoint, network, identity, cloud, zero-trust...
  keywords: [security, cyber, endpoint, ...]             # classification hints
  intake:                                                # ticker-intake matching
    priority: 7
    confidence: 0.74
    keywords: [cybersecurity, endpoint security, zero trust]
  holdings:                                              # what the basket holds
    - {ticker: CRWD, name: CrowdStrike, note: endpoint / cloud security}
  candidates:                                            # what it may hold
    - {ticker: QLYS, name: Qualys, note: vulnerability management}
```

Adding a basket means editing this one file. Everything downstream derives from it:
`market_config` (analysis window and holdings), `taxonomy_config` (paths, descriptions,
candidates), `category_workbench` (workstation state and search), `ticker_intake`
(keyword heuristics), and `sentiment_config` (news queries).

Quote any ticker that YAML 1.1 would read as a boolean — `ON`, `NO`, `YES`. The loader
raises rather than silently turning `ON` into `true`.

`backend/config/sentiment_queries.yaml` is now **optional overrides**, not a registry.
Baskets and holdings it does not mention get queries generated from their label,
keywords, and company names, so adding a ticker no longer fails the sentiment stage.
Run `python backend/sentiment_config.py` to see which queries are hand-tuned vs generated.

Validate the universe at any time:

```bash
backend/.venv/bin/python backend/universe.py
```

## Querying the data

`backend/datastore.py` exposes every pipeline CSV — plus the universe itself — as
DuckDB views, so questions can be asked at read time instead of being precomputed
into a dashboard payload.

```bash
backend/.venv/bin/python backend/datastore.py catalog
backend/.venv/bin/python backend/datastore.py schema basket_metrics
backend/.venv/bin/python backend/datastore.py query "SELECT ticker, basket FROM holdings LIMIT 5"
```

The `baskets`, `holdings`, `candidates`, and `benchmarks` tables come straight from
`universe.yaml`, so metrics can be joined against basket membership:

```sql
SELECT h.ticker, b.label, si.short_interest_change_pct, s.sentiment_state
FROM holdings h
JOIN baskets b ON b.id = h.basket
LEFT JOIN short_interest_metrics si ON si.ticker = h.ticker
LEFT JOIN ticker_news_sentiment s ON s.ticker = h.ticker AND s.basket = h.basket
WHERE si.short_interest_change_pct > 0
```

`query()` rejects non-read statements by default. Use `export-parquet` to materialize
all tables to `backend/data/parquet/` for faster repeat reads.

## Asking questions in plain language

`backend/agent.py` is a tool-calling loop over that data — type a question instead of
clicking through views.

```bash
npm run ask -- "how did metals do against semiconductors, and what drove the difference?"
npm run ask -- --trace "which holdings have rising short interest but positive sentiment?"
npm run ask                  # interactive
```

It needs `OPENAI_API_KEY` (read from `.env.local` at the project root). Override the
model with `AIO_AGENT_MODEL`; the default is `gpt-5.4-mini`, since multi-step tool
calling needs more than the nano tier the classification stages use. `--trace` prints
each tool call to stderr, which is the fastest way to see how a question was answered.

The tools live in `backend/agent_tools.py` and are provider-independent — plain
functions plus JSON schemas. Drive them by hand without any model:

```bash
python backend/agent_tools.py list_baskets
python backend/agent_tools.py basket_detail '{"basket": "oil_tankers"}'
python backend/agent_tools.py run_sql '{"sql": "SELECT * FROM basket_metrics LIMIT 3"}'
```

| Tool | What it does |
|---|---|
| `list_baskets` | Every basket with description, taxonomy path, holdings, headline performance |
| `describe_tables` | Table list, or exact columns for named tables |
| `run_sql` | Read-only DuckDB SELECT over everything |
| `compare_baskets` | Side-by-side on performance / price / fundamentals / positioning / sentiment |
| `basket_detail` | One basket: definition, metrics, sentiment, and every holding |

Tools return errors as `{"error": ...}` rather than raising, so a wrong column name
comes back as a readable message the model corrects on the next step instead of
killing the loop. Results are capped (`MAX_ROWS`, `MAX_RESULT_CHARS`) so one query
cannot swamp the context, and writes are refused.
