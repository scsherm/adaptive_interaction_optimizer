#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from category_workbench import price_refresh_status
from market_config import load_market_config, sync_config_end_date


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RUNS_DIR = ROOT / "runs"


ARTIFACTS = [
    ROOT / "README.md",
    ROOT / "config" / "baskets.yaml",
    ROOT / "config" / "taxonomy.yaml",
    DATA_DIR / "basket_definitions.csv",
    DATA_DIR / "source_metadata.csv",
    DATA_DIR / "basket_metrics.csv",
    DATA_DIR / "basket_daily.csv",
    DATA_DIR / "constituent_metrics.csv",
    DATA_DIR / "advanced_price_metrics.csv",
    DATA_DIR / "basket_advanced_price.csv",
    DATA_DIR / "cyclical_technical_metrics.csv",
    DATA_DIR / "basket_cyclical_technical.csv",
    DATA_DIR / "alpaca_market_status.json",
    DATA_DIR / "basket_breadth_daily.csv",
    DATA_DIR / "fundamentals_metrics.csv",
    DATA_DIR / "fundamentals_coverage.csv",
    DATA_DIR / "basket_fundamentals.csv",
    DATA_DIR / "short_volume_metrics.csv",
    DATA_DIR / "options_positioning_metrics.csv",
    DATA_DIR / "positioning_coverage.csv",
    DATA_DIR / "basket_positioning.csv",
    DATA_DIR / "short_interest_metrics.csv",
    DATA_DIR / "institutional_ownership_metrics.csv",
    DATA_DIR / "ownership_positioning_coverage.csv",
    DATA_DIR / "basket_ownership_positioning.csv",
    DATA_DIR / "analysis_summary.json",
    DATA_DIR / "analysis_brief.md",
    DATA_DIR / "qa_report.json",
    DATA_DIR / "qa_report.md",
    ROOT / "config" / "sentiment_queries.yaml",
    DATA_DIR / "sentiment" / "news_raw.csv",
    DATA_DIR / "sentiment" / "news_timeline_raw.csv",
    DATA_DIR / "sentiment" / "news_fetch_log.csv",
    DATA_DIR / "sentiment" / "news_llm_analysis.jsonl",
    DATA_DIR / "sentiment" / "news_llm_analysis.csv",
    DATA_DIR / "ticker_news_sentiment.csv",
    DATA_DIR / "basket_news_sentiment.csv",
    DATA_DIR / "sentiment_events.csv",
    DATA_DIR / "sentiment_summary.json",
    DATA_DIR / "sentiment_qa_report.json",
    DATA_DIR / "sentiment_qa_report.md",
    ROOT / "market-basket-dashboard.html",
    ROOT / "market-basket-analyst-workstation.html",
    ROOT / "market-basket-analyst-workstation-terminal.html",
    ROOT / "market-basket-sentiment-workstation.html",
]


def run_step(name: str, command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print(f"\n==> {name}")
    print(" ".join(command))
    return subprocess.run(command, cwd=ROOT, check=check)


def archive_run(
    run_id: str,
    refresh_prices: bool,
    refresh_fundamentals: bool,
    refresh_positioning: bool,
    refresh_ownership: bool,
    refresh_sentiment: bool,
) -> Path:
    config = load_market_config()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    for source in ARTIFACTS:
        if not source.exists():
            continue
        target_name = "dashboard.html" if source.name == "market-basket-dashboard.html" else source.name
        shutil.copy2(source, run_dir / target_name)

    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "start_date": config.start_date.isoformat(),
        "end_date": config.end_date.isoformat(),
        "refresh_prices": refresh_prices,
        "refresh_fundamentals": refresh_fundamentals,
        "refresh_positioning": refresh_positioning,
        "refresh_ownership": refresh_ownership,
        "refresh_sentiment": refresh_sentiment,
        "artifacts": sorted(path.name for path in run_dir.iterdir() if path.is_file()),
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the market basket analysis pipeline.")
    parser.add_argument(
        "--refresh-prices",
        action="store_true",
        help="Fetch fresh Yahoo chart JSON before analysis.",
    )
    parser.add_argument(
        "--keep-config-end-date",
        action="store_true",
        help="Keep config/baskets.yaml end_date unchanged instead of advancing to the latest completed U.S. equity session.",
    )
    parser.add_argument(
        "--no-auto-refresh-prices",
        action="store_true",
        help="Do not auto-enable --refresh-prices when cached Yahoo files are stale for the configured end_date.",
    )
    parser.add_argument(
        "--refresh-fundamentals",
        action="store_true",
        help="Fetch fresh SEC companyfacts before fundamentals analysis.",
    )
    parser.add_argument(
        "--refresh-positioning",
        action="store_true",
        help="Fetch fresh FINRA short-sale-volume and Cboe options snapshots.",
    )
    parser.add_argument(
        "--refresh-ownership",
        action="store_true",
        help="Fetch fresh true short-interest and institutional ownership snapshots.",
    )
    parser.add_argument(
        "--refresh-sentiment",
        action="store_true",
        help="Fetch fresh news sentiment rows before scoring.",
    )
    parser.add_argument(
        "--sentiment-provider",
        choices=["yahoo", "gdelt", "alpha_vantage", "all"],
        default="yahoo",
        help="News provider for --refresh-sentiment. Alpha Vantage supplies direct sentiment fields when ALPHAVANTAGE_API_KEY is set.",
    )
    parser.add_argument(
        "--sentiment-days",
        type=int,
        default=0,
        help="Optional sentiment lookback in days when --refresh-sentiment is used.",
    )
    parser.add_argument(
        "--sentiment-basket",
        default="",
        help="Optional basket id to refresh when --refresh-sentiment is used.",
    )
    parser.add_argument(
        "--sentiment-limit-queries",
        type=int,
        default=0,
        help="Optional safety cap for GDELT queries when --refresh-sentiment is used.",
    )
    parser.add_argument(
        "--sentiment-query-type",
        default="",
        help="Optional query type filter, e.g. company_specific, investor, demand_tailwind, or risk.",
    )
    parser.add_argument(
        "--sentiment-max-records",
        type=int,
        default=0,
        help="Optional max article records per provider query.",
    )
    parser.add_argument(
        "--sentiment-skip-timelines",
        action="store_true",
        help="Fetch article rows only and skip GDELT timeline modes.",
    )
    parser.add_argument(
        "--sentiment-skip-articles",
        action="store_true",
        help="Fetch timeline modes only and skip article rows. Applies to GDELT.",
    )
    parser.add_argument(
        "--skip-sentiment",
        action="store_true",
        help="Skip sentiment scoring, validation, and workstation rebuild.",
    )
    parser.add_argument(
        "--analyze-sentiment-llm",
        action="store_true",
        help="Classify cached raw sentiment articles with OpenAI before scoring. Requires OPENAI_API_KEY in the environment.",
    )
    parser.add_argument(
        "--sentiment-llm-limit",
        type=int,
        default=0,
        help="Optional cap for new OpenAI article classifications.",
    )
    parser.add_argument(
        "--sentiment-llm-workers",
        type=int,
        default=0,
        help="Parallel OpenAI article classification workers. Defaults to sentiment_llm_analyze.py setting.",
    )
    parser.add_argument(
        "--skip-dashboard",
        action="store_true",
        help="Skip rebuilding market-basket-dashboard.html.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip QA validation.",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Do not copy outputs into runs/<run-id>/.",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="Optional explicit run folder name. Defaults to a UTC timestamp.",
    )
    args = parser.parse_args()

    if not args.keep_config_end_date:
        sync_result = sync_config_end_date()
        if sync_result["dateChanged"]:
            print(
                "Updated analysis end date: "
                f"{sync_result['previousEndDate']} -> {sync_result['endDate']}"
            )
        elif sync_result["statusChanged"]:
            print(f"Updated analysis data status for {sync_result['endDate']}.")

    auto_price_reasons: list[str] = []
    if not args.refresh_prices and not args.no_auto_refresh_prices:
        price_status = price_refresh_status()
        if price_status["required"]:
            args.refresh_prices = True
            auto_price_reasons = price_status["reasons"]

    run_step("Write basket definitions and Yahoo download config", [sys.executable, "market_basket_analysis.py", "write-config"])
    if args.refresh_prices:
        if auto_price_reasons:
            print("\nAuto-enabled fresh prices:")
            for reason in auto_price_reasons:
                print(f"- {reason}")
        run_step("Fetch Yahoo chart data", ["curl", "-sS", "--config", str(DATA_DIR / "yahoo_chart_curl.cfg")])
    run_step("Compute normalized prices and metrics", [sys.executable, "market_basket_analysis.py", "analyze"])
    run_step("Compute advanced price metrics", [sys.executable, "advanced_price_metrics.py"])
    run_step("Compute cyclical technical metrics", [sys.executable, "cyclical_metrics.py"])
    if args.refresh_fundamentals:
        run_step("Write SEC ticker-index download config", [sys.executable, "fundamentals_metrics.py", "write-index-config"])
        run_step("Fetch SEC ticker index", ["curl", "-sS", "--config", str(DATA_DIR / "fundamentals" / "sec_index_curl.cfg")])
        run_step("Write SEC companyfacts download config", [sys.executable, "fundamentals_metrics.py", "write-companyfacts-config"])
        run_step("Fetch SEC companyfacts", ["curl", "-sS", "--config", str(DATA_DIR / "fundamentals" / "sec_companyfacts_curl.cfg")])
    run_step("Compute fundamentals metrics", [sys.executable, "fundamentals_metrics.py", "analyze"])
    run_step("Aggregate basket fundamentals", [sys.executable, "fundamentals_metrics.py", "aggregate"])
    if args.refresh_positioning:
        run_step("Write FINRA short-sale-volume config", [sys.executable, "positioning_metrics.py", "write-finra-config"])
        run_step("Fetch FINRA short-sale-volume files", ["curl", "-sS", "--config", str(DATA_DIR / "positioning" / "finra_regsho_curl.cfg")])
        run_step("Write Cboe options config", [sys.executable, "positioning_metrics.py", "write-cboe-config"])
        run_step("Fetch Cboe options snapshots", ["curl", "-sS", "--config", str(DATA_DIR / "positioning" / "cboe_options_curl.cfg")])
    run_step("Compute positioning metrics", [sys.executable, "positioning_metrics.py", "analyze"])
    if args.refresh_ownership:
        run_step(
            "Write true short-interest config",
            [sys.executable, "ownership_positioning_metrics.py", "write-short-config"],
        )
        run_step(
            "Fetch true short-interest snapshots",
            ["curl", "-sS", "--config", str(DATA_DIR / "ownership_positioning" / "stockanalysis_statistics_curl.cfg")],
        )
        run_step(
            "Write institutional ownership config",
            [sys.executable, "ownership_positioning_metrics.py", "write-institutional-config"],
        )
        run_step(
            "Fetch institutional ownership snapshots",
            ["curl", "-sS", "--config", str(DATA_DIR / "ownership_positioning" / "businessquant_institutional_curl.cfg")],
        )
    run_step("Compute ownership positioning metrics", [sys.executable, "ownership_positioning_metrics.py", "analyze"])
    should_build_workstation = (
        not args.skip_dashboard and (ROOT / "build_analyst_workstation.py").exists()
    )
    should_build_terminal_workstation = (
        should_build_workstation and (ROOT / "build_terminal_workstation.py").exists()
    )
    if not args.skip_dashboard:
        run_step("Build static dashboard", [sys.executable, "build_market_dashboard.py"])
    validation_result = None
    if not args.skip_validation:
        validation_result = run_step("Validate run", [sys.executable, "validate_run.py"], check=False)
    if should_build_workstation:
        run_step("Build analyst workstation", [sys.executable, "build_analyst_workstation.py"])
    if should_build_terminal_workstation:
        run_step("Build terminal analyst workstation", [sys.executable, "build_terminal_workstation.py"])
    sentiment_validation_result = None
    if not args.skip_sentiment and (ROOT / "config" / "sentiment_queries.yaml").exists():
        if args.refresh_sentiment:
            command = [sys.executable, "sentiment_news_fetch.py", "--refresh", "--provider", args.sentiment_provider]
            if args.sentiment_days:
                command.extend(["--days", str(args.sentiment_days)])
            if args.sentiment_basket:
                command.extend(["--basket", args.sentiment_basket])
            if args.sentiment_query_type:
                command.extend(["--query-type", args.sentiment_query_type])
            if args.sentiment_max_records:
                command.extend(["--max-records", str(args.sentiment_max_records)])
            if args.sentiment_limit_queries:
                command.extend(["--limit-queries", str(args.sentiment_limit_queries)])
            if args.sentiment_skip_timelines:
                command.append("--skip-timelines")
            if args.sentiment_skip_articles:
                command.append("--skip-articles")
            run_step("Fetch news sentiment data", command)
        if args.analyze_sentiment_llm:
            command = [sys.executable, "sentiment_llm_analyze.py"]
            if args.sentiment_basket:
                command.extend(["--basket", args.sentiment_basket])
            if args.sentiment_llm_limit:
                command.extend(["--limit", str(args.sentiment_llm_limit)])
            if args.sentiment_llm_workers:
                command.extend(["--workers", str(args.sentiment_llm_workers)])
            run_step("Analyze news sentiment with OpenAI", command)
        run_step("Compute sentiment signals", [sys.executable, "sentiment_signals.py"])
        sentiment_validation_result = run_step("Validate sentiment", [sys.executable, "validate_sentiment.py"], check=False)
        if not args.skip_dashboard:
            run_step("Build sentiment workstation", [sys.executable, "build_sentiment_workstation.py"])
    if validation_result is not None and validation_result.returncode != 0:
        return validation_result.returncode
    if sentiment_validation_result is not None and sentiment_validation_result.returncode != 0:
        return sentiment_validation_result.returncode
    if not args.no_archive:
        run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = archive_run(
            run_id,
            args.refresh_prices,
            args.refresh_fundamentals,
            args.refresh_positioning,
            args.refresh_ownership,
            args.refresh_sentiment,
        )
        print(f"\nArchived run: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
