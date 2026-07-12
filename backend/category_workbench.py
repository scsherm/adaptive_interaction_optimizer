#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from market_config import CONFIG_PATH, ROOT, latest_completed_us_equity_session, load_market_config, load_minimal_yaml
from taxonomy_config import load_effective_taxonomy


DATA_DIR = ROOT / "data"


TAXONOMY: dict[str, dict[str, Any]] = {
    "cybersecurity": {
        "description": "Endpoint, network, identity, cloud, zero-trust, exposure management, and application security.",
        "keywords": ["security", "cyber", "endpoint", "identity", "zero trust", "firewall", "exposure", "cloudflare"],
        "candidates": [
            ("CRWD", "CrowdStrike", "endpoint / cloud security"),
            ("PANW", "Palo Alto Networks", "platform security"),
            ("FTNT", "Fortinet", "network security"),
            ("ZS", "Zscaler", "zero-trust / SSE"),
            ("OKTA", "Okta", "identity security"),
            ("NET", "Cloudflare", "edge / application security"),
            ("S", "SentinelOne", "endpoint security"),
            ("TENB", "Tenable", "exposure management"),
            ("CHKP", "Check Point Software", "network security"),
            ("QLYS", "Qualys", "vulnerability management"),
            ("VRNS", "Varonis", "data security"),
            ("RPD", "Rapid7", "vulnerability / security analytics"),
            ("RDWR", "Radware", "application delivery / DDoS security"),
            ("GEN", "Gen Digital", "consumer identity / security"),
        ],
    },
    "btc_mining_ai_pivot": {
        "description": "Bitcoin miners and former miners pivoting capacity toward HPC, AI hosting, or data-center power assets.",
        "keywords": ["bitcoin mining", "miner", "hpc", "ai data center", "hosting", "hashrate"],
        "candidates": [
            ("IREN", "IREN", "bitcoin mining / AI data centers"),
            ("APLD", "Applied Digital", "AI data centers"),
            ("CORZ", "Core Scientific", "bitcoin mining / HPC hosting"),
            ("CIFR", "Cipher Mining", "bitcoin mining / HPC optionality"),
            ("CLSK", "CleanSpark", "bitcoin mining"),
            ("WULF", "TeraWulf", "bitcoin mining / HPC optionality"),
            ("MARA", "MARA Holdings", "bitcoin mining"),
            ("RIOT", "Riot Platforms", "bitcoin mining"),
            ("BTDR", "Bitdeer Technologies", "bitcoin mining / cloud hashrate"),
            ("HUT", "Hut 8", "bitcoin mining / HPC"),
            ("HIVE", "HIVE Digital", "bitcoin mining / GPU cloud"),
            ("BITF", "Bitfarms", "bitcoin mining"),
            ("CAN", "Canaan", "bitcoin mining ASICs"),
        ],
    },
    "software": {
        "description": "Large-cap software, SaaS, data infrastructure, observability, enterprise workflow, and AI application platforms.",
        "keywords": ["software", "saas", "cloud", "data", "workflow", "enterprise", "analytics", "observability"],
        "candidates": [
            ("MSFT", "Microsoft", "large-cap software / cloud"),
            ("ORCL", "Oracle", "database / cloud infrastructure software"),
            ("CRM", "Salesforce", "enterprise SaaS"),
            ("NOW", "ServiceNow", "workflow SaaS"),
            ("ADBE", "Adobe", "creative / document software"),
            ("SNOW", "Snowflake", "data cloud"),
            ("DDOG", "Datadog", "observability"),
            ("PLTR", "Palantir", "AI / analytics software"),
            ("TEAM", "Atlassian", "collaboration software"),
            ("WDAY", "Workday", "enterprise SaaS"),
            ("INTU", "Intuit", "financial software"),
            ("MDB", "MongoDB", "database software"),
            ("ESTC", "Elastic", "search / observability software"),
            ("SHOP", "Shopify", "commerce software"),
            ("APP", "AppLovin", "advertising / app software"),
        ],
    },
    "semiconductors": {
        "description": "AI accelerators, CPUs/GPUs, memory, foundry, semiconductor equipment, analog, networking, and edge chips.",
        "keywords": ["semiconductor", "chip", "foundry", "memory", "lithography", "gpu", "accelerator", "analog"],
        "candidates": [
            ("NVDA", "Nvidia", "AI accelerators"),
            ("AMD", "AMD", "CPUs / GPUs"),
            ("AVGO", "Broadcom", "AI networking / custom silicon"),
            ("TSM", "TSMC ADR", "foundry"),
            ("ASML", "ASML ADR", "lithography"),
            ("MU", "Micron", "memory"),
            ("MRVL", "Marvell", "data-center semis"),
            ("QCOM", "Qualcomm", "mobile / edge semis"),
            ("INTC", "Intel", "CPUs / foundry"),
            ("AMAT", "Applied Materials", "semiconductor equipment"),
            ("LRCX", "Lam Research", "semiconductor equipment"),
            ("KLAC", "KLA", "process control / metrology"),
            ("ADI", "Analog Devices", "analog semiconductors"),
            ("TXN", "Texas Instruments", "analog / embedded semis"),
            ("ARM", "Arm Holdings", "CPU IP"),
            ("ON", "ON Semiconductor", "power / auto semis"),
        ],
    },
    "metals": {
        "description": "Copper, aluminum, steel, iron ore, base metals, and diversified miners.",
        "keywords": ["copper", "aluminum", "steel", "mining", "metals", "iron ore", "base metals"],
        "candidates": [
            ("FCX", "Freeport-McMoRan", "copper / gold mining"),
            ("SCCO", "Southern Copper", "copper mining"),
            ("AA", "Alcoa", "aluminum"),
            ("TECK", "Teck Resources", "base metals"),
            ("RIO", "Rio Tinto ADR", "diversified mining"),
            ("BHP", "BHP ADR", "diversified mining"),
            ("CLF", "Cleveland-Cliffs", "steel / iron ore"),
            ("NUE", "Nucor", "steel"),
            ("VALE", "Vale ADR", "iron ore / base metals"),
            ("STLD", "Steel Dynamics", "steel"),
            ("CMC", "Commercial Metals", "steel / rebar"),
            ("MT", "ArcelorMittal ADR", "global steel"),
            ("HBM", "Hudbay Minerals", "copper / base metals"),
        ],
    },
    "fertilizer": {
        "description": "Fertilizer, crop nutrients, nitrogen, phosphate, potash, and adjacent agricultural input producers.",
        "keywords": ["fertilizer", "crop nutrients", "nitrogen", "potash", "phosphate", "ammonia", "ag inputs"],
        "candidates": [
            ("NTR", "Nutrien", "potash / nitrogen / ag retail"),
            ("MOS", "Mosaic", "phosphate / potash fertilizer"),
            ("CF", "CF Industries", "nitrogen fertilizer"),
            ("ICL", "ICL Group", "potash / specialty fertilizers"),
            ("SQM", "SQM", "specialty plant nutrition / potash"),
            ("UAN", "CVR Partners", "nitrogen fertilizer MLP"),
            ("LXU", "LSB Industries", "ammonia / nitrogen products"),
            ("SMG", "Scotts Miracle-Gro", "consumer lawn and garden fertilizer"),
            ("CTVA", "Corteva", "seeds / crop protection; ag-input adjacent"),
            ("FMC", "FMC", "crop protection; ag-input adjacent"),
            ("AVD", "American Vanguard", "crop protection; ag-input adjacent"),
            ("IPI", "Intrepid Potash", "potash / specialty fertilizer"),
        ],
    },
    "photonics": {
        "description": "Optical networking, lasers, optical components, photonic process tools, and compound semiconductor substrates.",
        "keywords": ["optical", "photonics", "laser", "fiber", "transceiver", "datacenter optical", "compound semiconductor"],
        "candidates": [
            ("COHR", "Coherent", "lasers / optical components"),
            ("LITE", "Lumentum", "optical components"),
            ("FN", "Fabrinet", "optical manufacturing"),
            ("AAOI", "Applied Optoelectronics", "datacenter optical modules"),
            ("IPGP", "IPG Photonics", "fiber lasers"),
            ("MKSI", "MKS Instruments", "photonic / process tools"),
            ("HLIT", "Harmonic", "optical/video networking"),
            ("AXTI", "AXT", "compound semiconductor substrates"),
            ("CIEN", "Ciena", "optical networking"),
            ("VIAV", "Viavi Solutions", "optical test / measurement"),
            ("OLED", "Universal Display", "display materials / emitters"),
            ("ONTO", "Onto Innovation", "process control / inspection"),
            ("COHU", "Cohu", "semiconductor test with photonics exposure"),
        ],
    },
    "quantum": {
        "description": "Pure-play and high-beta quantum computing, quantum sensing, and post-quantum security companies.",
        "keywords": ["quantum", "qubit", "trapped ion", "neutral atom", "annealing", "post-quantum", "quantum-safe"],
        "candidates": [
            ("IONQ", "IonQ", "trapped-ion quantum computing"),
            ("RGTI", "Rigetti Computing", "superconducting quantum computing"),
            ("QBTS", "D-Wave Quantum", "quantum annealing / systems"),
            ("QUBT", "Quantum Computing Inc.", "quantum software / photonics"),
            ("INFQ", "Infleqtion", "neutral-atom quantum computing / sensing"),
            ("QNC", "Quantum eMotion", "quantum cybersecurity / random generation"),
            ("ARQQ", "Arqit Quantum", "quantum-safe encryption"),
            ("LAES", "SEALSQ", "post-quantum security semiconductors"),
            ("QMCO", "Quantum Corporation", "storage systems; name-adjacent, not a quantum computing pure play"),
            ("FORM", "FormFactor", "cryogenic probe cards / quantum test infrastructure"),
            ("HON", "Honeywell", "majority owner of Quantinuum; diluted mega-cap exposure"),
            ("IBM", "IBM", "quantum computing platform; diluted mega-cap exposure"),
        ],
    },
    "crypto": {
        "description": "Liquid cryptoassets tracked as Yahoo USD pairs.",
        "keywords": ["cryptoasset", "crypto", "blockchain", "token", "usd pair"],
        "candidates": [
            ("BTC-USD", "Bitcoin", "cryptoasset"),
            ("ETH-USD", "Ethereum", "cryptoasset"),
            ("SOL-USD", "Solana", "cryptoasset"),
            ("BNB-USD", "BNB", "cryptoasset"),
            ("XRP-USD", "XRP", "cryptoasset"),
            ("ADA-USD", "Cardano", "cryptoasset"),
            ("DOGE-USD", "Dogecoin", "cryptoasset"),
            ("LINK-USD", "Chainlink", "cryptoasset"),
            ("AVAX-USD", "Avalanche", "cryptoasset"),
            ("DOT-USD", "Polkadot", "cryptoasset"),
            ("LTC-USD", "Litecoin", "cryptoasset"),
            ("BCH-USD", "Bitcoin Cash", "cryptoasset"),
            ("UNI-USD", "Uniswap", "cryptoasset"),
            ("AAVE-USD", "Aave", "cryptoasset"),
            ("NEAR-USD", "NEAR Protocol", "cryptoasset"),
        ],
    },
    "oil": {
        "description": "Integrated oil, E&P, oilfield services, refining, and energy infrastructure tied primarily to crude.",
        "keywords": ["oil", "energy", "e&p", "refining", "oilfield", "integrated oil", "crude"],
        "candidates": [
            ("XOM", "Exxon Mobil", "integrated oil"),
            ("CVX", "Chevron", "integrated oil"),
            ("COP", "ConocoPhillips", "E&P"),
            ("EOG", "EOG Resources", "E&P"),
            ("OXY", "Occidental Petroleum", "E&P"),
            ("SLB", "SLB", "oilfield services"),
            ("HAL", "Halliburton", "oilfield services"),
            ("VLO", "Valero", "refining"),
            ("MPC", "Marathon Petroleum", "refining"),
            ("PSX", "Phillips 66", "refining / midstream"),
            ("DVN", "Devon Energy", "E&P"),
            ("FANG", "Diamondback Energy", "E&P"),
            ("BKR", "Baker Hughes", "oilfield services / LNG equipment"),
        ],
    },
    "oil_tankers": {
        "description": "Crude and product tanker owners/operators with listed U.S. or ADR tickers where practical.",
        "keywords": ["tanker", "crude tanker", "product tanker", "shipping", "marine transport"],
        "candidates": [
            ("FRO", "Frontline", "crude/product tankers"),
            ("DHT", "DHT Holdings", "crude tankers"),
            ("STNG", "Scorpio Tankers", "product tankers"),
            ("TNK", "Teekay Tankers", "crude/product tankers"),
            ("INSW", "International Seaways", "crude/product tankers"),
            ("NAT", "Nordic American Tankers", "crude tankers"),
            ("CMBT", "CMB.TECH", "former Euronav crude tanker fleet / marine technology"),
            ("TEN", "Tsakos Energy Navigation", "crude/product tankers"),
            ("ASC", "Ardmore Shipping", "product tankers"),
            ("TRMD", "TORM", "product tankers"),
            ("SFL", "SFL Corporation", "shipping lessor with tanker exposure"),
        ],
    },
    "rare_earth_minerals": {
        "description": "Rare earth producers/developers and strategic/critical minerals companies with related exposure.",
        "keywords": ["rare earth", "critical minerals", "strategic metals", "antimony", "uranium", "mineral development"],
        "candidates": [
            ("MP", "MP Materials", "rare earth producer"),
            ("UUUU", "Energy Fuels", "uranium / rare earth processing"),
            ("UAMY", "United States Antimony", "critical minerals"),
            ("TMRC", "Texas Mineral Resources", "rare earth development"),
            ("LYSDY", "Lynas Rare Earths ADR", "rare earth producer"),
            ("AREC", "American Resources", "critical minerals / carbon"),
            ("CRML", "Critical Metals", "critical minerals development"),
            ("REMX", "VanEck Rare Earth/Strategic Metals ETF", "thematic ETF anchor"),
            ("ABAT", "American Battery Technology", "battery metals / recycling"),
            ("PLL", "Piedmont Lithium", "critical battery minerals"),
            ("LAC", "Lithium Americas", "critical battery minerals"),
            ("NIOBF", "NioCorp Developments", "critical minerals development"),
        ],
    },
    "construction": {
        "description": "Homebuilders, construction equipment, infrastructure construction, aggregates, and building materials.",
        "keywords": ["homebuilding", "construction", "equipment rental", "aggregates", "materials", "infrastructure"],
        "candidates": [
            ("DHI", "D.R. Horton", "homebuilding"),
            ("LEN", "Lennar", "homebuilding"),
            ("PHM", "PulteGroup", "homebuilding"),
            ("CAT", "Caterpillar", "construction equipment"),
            ("URI", "United Rentals", "equipment rental"),
            ("VMC", "Vulcan Materials", "aggregates"),
            ("MLM", "Martin Marietta Materials", "aggregates"),
            ("PWR", "Quanta Services", "infrastructure construction"),
            ("TOL", "Toll Brothers", "homebuilding"),
            ("KBH", "KB Home", "homebuilding"),
            ("NVR", "NVR", "homebuilding"),
            ("BLD", "TopBuild", "building insulation / installation"),
            ("MAS", "Masco", "building products"),
            ("EXP", "Eagle Materials", "cement / wallboard"),
            ("ROAD", "Construction Partners", "road construction"),
        ],
    },
    "power_grid": {
        "description": "Power generation, electrical equipment, grid construction, utilities, nuclear/power producers, and grid storage.",
        "keywords": ["power", "grid", "electrical", "utility", "nuclear", "generation", "energy storage", "transmission"],
        "candidates": [
            ("GEV", "GE Vernova", "power generation / grid equipment"),
            ("ETN", "Eaton", "electrical equipment"),
            ("HUBB", "Hubbell", "electrical / grid equipment"),
            ("PWR", "Quanta Services", "grid construction"),
            ("VST", "Vistra", "power generation"),
            ("CEG", "Constellation Energy", "nuclear / power generation"),
            ("NEE", "NextEra Energy", "utility / renewables"),
            ("NRG", "NRG Energy", "power generation / retail"),
            ("POWL", "Powell Industries", "electrical equipment / power systems"),
            ("AMSC", "American Superconductor", "grid systems"),
            ("GNRC", "Generac", "backup power / distributed energy"),
            ("FLNC", "Fluence Energy", "grid-scale energy storage"),
            ("AEP", "American Electric Power", "regulated utility / transmission"),
            ("SO", "Southern Company", "regulated utility / power generation"),
            ("DUK", "Duke Energy", "regulated utility"),
        ],
    },
}


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def coverage_indexes() -> dict[str, set[str]]:
    source = {row["ticker"] for row in read_csv("source_metadata.csv") if row.get("ticker")}
    fundamentals = {
        row["ticker"]
        for row in read_csv("fundamentals_metrics.csv")
        if row.get("ticker") and row.get("coverage_status") not in {"", "missing"}
    }
    options = {
        row["ticker"]
        for row in read_csv("options_positioning_metrics.csv")
        if row.get("ticker") and row.get("coverage_status") not in {"", "missing"}
    }
    short_interest = {
        row["ticker"]
        for row in read_csv("short_interest_metrics.csv")
        if row.get("ticker") and row.get("coverage_status") not in {"", "missing"}
    }
    institutional = {
        row["ticker"]
        for row in read_csv("institutional_ownership_metrics.csv")
        if row.get("ticker") and row.get("coverage_status") not in {"", "missing"}
    }
    return {
        "price": source,
        "fundamentals": fundamentals,
        "options": options,
        "shortInterest": short_interest,
        "institutional": institutional,
    }


def candidate_map(category_id: str) -> dict[str, dict[str, str]]:
    taxonomy = load_effective_taxonomy(TAXONOMY).get(category_id)
    if not taxonomy:
        return {}
    return {
        ticker.upper(): {"ticker": ticker.upper(), "name": name, "note": note}
        for ticker, name, note in taxonomy["candidates"]
    }


def current_holdings() -> dict[str, list[dict[str, str]]]:
    config = load_market_config()
    return {
        basket.id: [
            {"ticker": holding.ticker, "name": holding.name, "note": holding.note}
            for holding in basket.holdings
        ]
        for basket in config.baskets
    }


def price_refresh_status() -> dict[str, Any]:
    config = load_market_config()
    latest_session = latest_completed_us_equity_session()
    source_rows = {
        row["ticker"].upper(): row
        for row in read_csv("source_metadata.csv")
        if row.get("ticker")
    }
    configured = sorted(
        {
            *(holding.ticker.upper() for holding in config.holdings),
            *(benchmark.ticker.upper() for benchmark in config.benchmarks),
        }
    )
    start = config.start_date.isoformat()
    end = config.end_date.isoformat()
    end_date_behind_latest = config.end_date < latest_session
    missing = [ticker for ticker in configured if ticker not in source_rows]
    stale_prices = []
    late_history_gaps = []
    minor_calendar_gaps = []
    for ticker in configured:
        if ticker not in source_rows:
            continue
        last_date = source_rows[ticker].get("last_date", "")
        if last_date and date.fromisoformat(last_date) < config.end_date:
            stale_prices.append({"ticker": ticker, "lastDate": last_date})
        if not source_rows[ticker].get("first_date", ""):
            continue
        first_date = source_rows[ticker]["first_date"]
        if first_date <= start:
            continue
        gap = (date.fromisoformat(first_date) - config.start_date).days
        item = {"ticker": ticker, "firstDate": first_date, "gapDays": gap}
        if gap > 7:
            late_history_gaps.append(item)
        else:
            minor_calendar_gaps.append(item)
    broad_cache_gap = len(late_history_gaps) > max(2, round(len(configured) * 0.1))
    later_than_start = late_history_gaps if broad_cache_gap else []
    source_history_gaps = [] if broad_cache_gap else late_history_gaps
    cached_first_dates = [
        row.get("first_date", "")
        for row in source_rows.values()
        if row.get("first_date", "")
    ]
    reasons = []
    if later_than_start:
        earliest = min(item["firstDate"] for item in later_than_start if item["firstDate"])
        reasons.append(
            f"Configured start date {start} is earlier than cached price history for "
            f"{len(later_than_start)} configured tickers; earliest cached start is {earliest}."
        )
    if missing:
        examples = ", ".join(missing[:6])
        suffix = "..." if len(missing) > 6 else ""
        reasons.append(f"{len(missing)} configured tickers have no cached price data: {examples}{suffix}")
    broad_stale_cache = len(stale_prices) > max(2, round(len(configured) * 0.1))
    refresh_stale_prices = stale_prices if broad_stale_cache else []
    source_stale_prices = [] if broad_stale_cache else stale_prices
    if refresh_stale_prices:
        examples = ", ".join(f"{item['ticker']} {item['lastDate']}" for item in refresh_stale_prices[:6])
        suffix = "..." if len(stale_prices) > 6 else ""
        reasons.append(
            f"{len(refresh_stale_prices)} configured tickers have cached prices older than configured end date {end}: "
            f"{examples}{suffix}"
        )
    if end_date_behind_latest:
        reasons.append(
            f"Configured end date {end} is behind the latest completed U.S. equity session "
            f"{latest_session.isoformat()}."
        )
    return {
        "required": bool(missing or later_than_start or refresh_stale_prices or end_date_behind_latest),
        "configuredStartDate": start,
        "configuredEndDate": end,
        "latestCompletedSession": latest_session.isoformat(),
        "endDateBehindLatest": end_date_behind_latest,
        "earliestCachedDate": min(cached_first_dates) if cached_first_dates else "",
        "missingTickers": missing,
        "stalePrices": stale_prices,
        "refreshStalePrices": refresh_stale_prices,
        "sourceStalePrices": source_stale_prices,
        "laterThanStart": later_than_start,
        "sourceHistoryGaps": source_history_gaps,
        "minorCalendarGaps": minor_calendar_gaps,
        "reasons": reasons,
    }


def category_state() -> dict[str, Any]:
    config = load_market_config()
    holdings = current_holdings()
    taxonomy_by_id = load_effective_taxonomy(TAXONOMY)
    categories = []
    for basket in config.baskets:
        taxonomy = taxonomy_by_id.get(basket.id, {})
        categories.append(
            {
                "id": basket.id,
                "label": basket.label,
                "short": basket.short,
                "color": basket.color,
                "taxonomyPath": taxonomy.get("path", []),
                "description": taxonomy.get("description", ""),
                "keywords": taxonomy.get("keywords", []),
                "holdings": holdings.get(basket.id, []),
                "candidateCount": len(taxonomy.get("candidates", [])),
            }
        )
    return {
        "methodology": {
            "startDate": config.start_date.isoformat(),
            "endDate": config.end_date.isoformat(),
            "weighting": config.weighting,
            "priceField": config.price_field,
        },
        "categories": categories,
        "priceRefresh": price_refresh_status(),
    }


def search_category(category_id: str, query: str = "") -> list[dict[str, Any]]:
    taxonomy = load_effective_taxonomy(TAXONOMY).get(category_id)
    if not taxonomy:
        raise KeyError(f"Unknown category: {category_id}")
    query = query.strip().upper()
    holding_tickers = {row["ticker"].upper() for row in current_holdings().get(category_id, [])}
    coverage = coverage_indexes()
    results = []
    for ticker, name, note in taxonomy["candidates"]:
        ticker = ticker.upper()
        haystack = f"{ticker} {name} {note}".upper()
        if query and query not in haystack:
            continue
        coverage_flags = {key: ticker in values for key, values in coverage.items()}
        coverage_score = round(sum(1 for value in coverage_flags.values() if value) / len(coverage_flags) * 100)
        results.append(
            {
                "ticker": ticker,
                "name": name,
                "note": note,
                "reason": f"Predetermined {taxonomy['description']} taxonomy: {note}.",
                "confidence": 100 if ticker in holding_tickers else 86,
                "alreadyInBasket": ticker in holding_tickers,
                "coverage": coverage_flags,
                "coverageScore": coverage_score,
            }
        )
    return sorted(results, key=lambda row: (not row["alreadyInBasket"], -row["coverageScore"], row["ticker"]))


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


def load_config_data() -> dict[str, Any]:
    return deepcopy(load_minimal_yaml(CONFIG_PATH))


def save_config_data(data: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(dump_baskets_yaml(data))


def set_start_date(value: str) -> dict[str, Any]:
    parsed = date.fromisoformat(value)
    data = load_config_data()
    end_date = date.fromisoformat(str(data["methodology"]["end_date"]))
    if parsed > end_date:
        raise ValueError(f"Start date {parsed.isoformat()} cannot be after end date {end_date.isoformat()}")
    data["methodology"]["start_date"] = parsed.isoformat()
    save_config_data(data)
    return category_state()


def add_candidate(category_id: str, ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()
    candidates = candidate_map(category_id)
    if ticker not in candidates:
        raise ValueError(f"{ticker} is not eligible for {category_id} under the predetermined taxonomy")
    data = load_config_data()
    for basket in data["baskets"]:
        if basket["id"] != category_id:
            continue
        existing = {row["ticker"].upper() for row in basket["holdings"]}
        if ticker not in existing:
            basket["holdings"].append(candidates[ticker])
        save_config_data(data)
        return category_state()
    raise KeyError(f"Unknown category: {category_id}")


def remove_holding(category_id: str, ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()
    data = load_config_data()
    for basket in data["baskets"]:
        if basket["id"] != category_id:
            continue
        if len(basket["holdings"]) <= 1:
            raise ValueError("A category must keep at least one holding")
        basket["holdings"] = [row for row in basket["holdings"] if row["ticker"].upper() != ticker]
        save_config_data(data)
        return category_state()
    raise KeyError(f"Unknown category: {category_id}")


def validate_taxonomy() -> list[str]:
    config = load_market_config()
    taxonomy_by_id = load_effective_taxonomy(TAXONOMY)
    problems = []
    for basket in config.baskets:
        candidates = {
            ticker.upper(): {"ticker": ticker.upper(), "name": name, "note": note}
            for ticker, name, note in taxonomy_by_id.get(basket.id, {}).get("candidates", [])
        }
        if not candidates:
            problems.append(f"Missing taxonomy for {basket.id}")
            continue
        for holding in basket.holdings:
            if holding.ticker.upper() not in candidates:
                problems.append(f"{holding.ticker} in {basket.id} is not represented in category taxonomy")
    return problems


def main() -> int:
    problems = validate_taxonomy()
    if problems:
        print(json.dumps({"status": "FAIL", "problems": problems}, indent=2))
        return 1
    print(json.dumps({"status": "PASS", "categories": len(TAXONOMY)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
