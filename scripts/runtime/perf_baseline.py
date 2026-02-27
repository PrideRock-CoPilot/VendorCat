from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import django
from django.core.management import call_command
from django.test import Client

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vendorcatalog_rebuild.settings")

django.setup()

from apps.core.config.env import get_runtime_settings  # noqa: E402
from apps.core.observability import evaluate_alert_thresholds  # noqa: E402
from apps.core.sql.adapter import create_sql_adapter  # noqa: E402
from apps.help_center.models import HelpArticle  # noqa: E402
from apps.reports.models import ReportRun  # noqa: E402


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * percentile
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = rank - lower_index
    return sorted_values[lower_index] + (sorted_values[upper_index] - sorted_values[lower_index]) * fraction


def _run_iterations(client: Client, endpoint_call: Callable[[], None], iterations: int) -> list[float]:
    durations: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        endpoint_call()
        durations.append((time.perf_counter() - started) * 1000)
    return durations


def _ensure_baseline_data() -> None:
    if not HelpArticle.objects.filter(slug="perf-baseline-help").exists():  # type: ignore[attr-defined]
        HelpArticle.objects.create(  # type: ignore[attr-defined]
            article_id=str(uuid.uuid4()),
            slug="perf-baseline-help",
            title="Performance Baseline Article",
            markdown_body="Performance baseline article content",
            rendered_html="<p>Performance baseline article content</p>",
            published=True,
            article_title="Performance Baseline Article",
            category="faq",
            content_markdown="Performance baseline article content",
            is_published=True,
            author="perf-harness",
        )

    if not ReportRun.objects.filter(report_run_id="perf-baseline-run").exists():  # type: ignore[attr-defined]
        ReportRun.objects.create(  # type: ignore[attr-defined]
            report_run_id="perf-baseline-run",
            report_code="perf_report",
            report_type="perf_report",
            report_name="Performance Baseline Report",
            report_format="preview",
            status="completed",
            triggered_by="perf-harness",
            scheduled_time=django.utils.timezone.now(),
            row_count=10,
            filters_json="{}",
            warnings_json="[]",
        )


def _ensure_perf_table() -> None:
    settings = get_runtime_settings()
    adapter = create_sql_adapter(settings)
    adapter.execute(
        """
        CREATE TABLE IF NOT EXISTS vc_perf_baseline (
            baseline_id VARCHAR PRIMARY KEY,
            scenario_key VARCHAR NOT NULL,
            runtime_profile VARCHAR NOT NULL,
            p50_ms DOUBLE NOT NULL,
            p95_ms DOUBLE NOT NULL,
            sample_size INTEGER NOT NULL,
            run_id VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _store_result(scenario_key: str, p50_ms: float, p95_ms: float, sample_size: int, run_id: str) -> None:
    settings = get_runtime_settings()
    adapter = create_sql_adapter(settings)
    adapter.execute(
        """
        INSERT INTO vc_perf_baseline (baseline_id, scenario_key, runtime_profile, p50_ms, p95_ms, sample_size, run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            scenario_key,
            settings.runtime_profile,
            float(p50_ms),
            float(p95_ms),
            int(sample_size),
            run_id,
        ),
    )


def _markdown_report(run_id: str, runtime_profile: str, summary: dict[str, tuple[float, float, int]]) -> str:
    observed = {key: values[1] for key, values in summary.items()}
    threshold_eval = evaluate_alert_thresholds(runtime_profile, observed)

    lines = [
        "# Performance Baseline Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Runtime Profile: `{runtime_profile}`",
        "",
        "| Scenario | p50 (ms) | p95 (ms) | Samples | Threshold (ms) | Pass |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]

    for scenario_key in ["search", "import_preview", "report_preview"]:
        p50_ms, p95_ms, samples = summary[scenario_key]
        threshold = threshold_eval[scenario_key]["threshold_ms"]
        is_pass = "yes" if threshold_eval[scenario_key]["pass"] else "no"
        lines.append(
            f"| {scenario_key} | {p50_ms:.2f} | {p95_ms:.2f} | {samples} | {threshold:.0f} | {is_pass} |"
        )

    lines.append("")
    return "\n".join(lines)


def run_perf_baseline(iterations: int, output_path: Path) -> int:
    call_command("migrate", verbosity=0, interactive=False)
    _ensure_baseline_data()
    _ensure_perf_table()

    client = Client()
    headers = {
        "HTTP_X_FORWARDED_USER": "perf@example.com",
        "HTTP_X_FORWARDED_GROUPS": "vendor_admin,ops_observer",
    }

    scenarios: dict[str, Callable[[], None]] = {
        "search": lambda: client.get("/api/v1/help/search?q=performance", **headers),
        "import_preview": lambda: client.get("/api/v1/imports/jobs", **headers),
        "report_preview": lambda: client.get("/api/v1/reports/runs", **headers),
    }

    run_id = str(uuid.uuid4())
    summary: dict[str, tuple[float, float, int]] = {}

    for scenario_key, scenario_call in scenarios.items():
        timings = _run_iterations(client, scenario_call, iterations)
        p50_ms = statistics.median(timings)
        p95_ms = _percentile(timings, 0.95)
        summary[scenario_key] = (p50_ms, p95_ms, len(timings))
        _store_result(scenario_key, p50_ms, p95_ms, len(timings), run_id)

    runtime_profile = get_runtime_settings().runtime_profile
    report = _markdown_report(run_id, runtime_profile, summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VendorCatalog performance baseline scenarios")
    parser.add_argument("--iterations", type=int, default=15)
    parser.add_argument("--output", type=str, default="docs/rebuild/performance_baseline.md")
    args = parser.parse_args()

    if args.iterations <= 0:
        print("iterations must be > 0")
        return 1

    output_path = Path(args.output)
    return run_perf_baseline(args.iterations, output_path)


if __name__ == "__main__":
    raise SystemExit(main())
