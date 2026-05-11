"""Knowledge tree integrity validator.

Per CC build directive section 10: run between every Phase-1 branch and
every Phase-2 config completion. Confirms the tree didn't degrade during
ingestion. Surfaces threshold failures so the runner pauses for John.

Checks (each returns a metric + verdict):
    1. orphan_facts_at_root  — facts with topic = root parent (not a leaf)
    2. uncategorized_rate    — % of facts in 'uncategorized' (overall + new)
    3. parent_child_ratios   — leaf fact counts vs parent fact counts
    4. leaf_explosion        — count of zero/very-thin leaves
    5. supersede_rate        — % of newly-superseded facts in last batch

Thresholds match the directive:
    - uncategorized rate (NEW facts only) > 10% → fail
    - supersede rate per branch > 80% → escalate
    - leaf explosion: > 5 new zero-fact topics in one pass → flag

The runner calls validate_after_branch(branch_name, ingest_stats) which
returns a TreeValidationReport. If `report.passed` is False, the runner
MUST pause and surface to John.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger("charles.tree_validator")


@dataclass
class TreeValidationReport:
    branch_or_config: str
    passed: bool = True
    metrics: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, reason: str) -> None:
        self.passed = False
        self.failures.append(reason)

    def warn(self, reason: str) -> None:
        self.warnings.append(reason)

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        lines = [f"[{verdict}] tree validation after {self.branch_or_config}"]
        for k, v in self.metrics.items():
            lines.append(f"  {k}: {v}")
        for f in self.failures:
            lines.append(f"  ❌ {f}")
        for w in self.warnings:
            lines.append(f"  ⚠️  {w}")
        return "\n".join(lines)


def _conn():
    """Reuse the same DB connection pattern as core.memory."""
    from core.memory import _conn as memory_conn
    return memory_conn()


def check_orphan_facts(report: TreeValidationReport) -> int:
    """Count facts whose topic is a PARENT in the taxonomy (orphans —
    these should have routed to a leaf). Returns count.
    """
    with _conn() as c:
        rows = c.execute("""
            SELECT t.name, COUNT(f.id) AS n
              FROM long_term_facts f
              JOIN topics t ON f.topic = t.name
             WHERE t.parent_topic_id IS NULL
               AND t.name != 'system_health'
               AND t.name != 'uncategorized'
               AND (f.tags NOT LIKE '%superseded%')
          GROUP BY t.name
            HAVING n > 0
        """).fetchall()
    by_parent = {r["name"]: r["n"] for r in rows}
    total = sum(by_parent.values())
    report.metrics["orphan_facts_at_root"] = total
    report.metrics["orphan_by_parent"] = by_parent
    return total


def check_uncategorized_rate(
    report: TreeValidationReport,
    *,
    new_only_since: str | None = None,
    threshold: float = 0.10,
) -> float:
    """Rate of facts under 'uncategorized'. If new_only_since is set,
    measures only facts created since that ISO timestamp. Threshold
    enforced ONLY on the new-only count (per directive)."""
    with _conn() as c:
        if new_only_since:
            new_total = c.execute(
                "SELECT COUNT(*) FROM long_term_facts WHERE created_at > ?",
                (new_only_since,),
            ).fetchone()[0]
            new_unc = c.execute(
                "SELECT COUNT(*) FROM long_term_facts "
                "WHERE created_at > ? AND topic = 'uncategorized'",
                (new_only_since,),
            ).fetchone()[0]
            new_rate = (new_unc / new_total) if new_total else 0.0
            report.metrics["new_uncategorized_rate"] = round(new_rate, 4)
            report.metrics["new_uncategorized_count"] = new_unc
            report.metrics["new_total"] = new_total
            if new_rate > threshold:
                report.fail(
                    f"new uncategorized rate {new_rate:.1%} exceeds {threshold:.0%}"
                )
            return new_rate
        # Overall rate (no threshold gate, just a metric)
        total = c.execute("SELECT COUNT(*) FROM long_term_facts").fetchone()[0]
        unc = c.execute(
            "SELECT COUNT(*) FROM long_term_facts WHERE topic = 'uncategorized'"
        ).fetchone()[0]
        rate = (unc / total) if total else 0.0
        report.metrics["uncategorized_rate"] = round(rate, 4)
        report.metrics["uncategorized_count"] = unc
        return rate


def check_parent_child_ratios(report: TreeValidationReport) -> dict:
    """For each parent topic, count leaves and facts. Healthy = no parent
    has a single leaf doing all the work, no parent is empty."""
    with _conn() as c:
        rows = c.execute("""
            SELECT p.name AS parent, t.name AS leaf, t.fact_count
              FROM topics t JOIN topics p ON t.parent_topic_id = p.id
          ORDER BY p.name, t.fact_count DESC
        """).fetchall()
    by_parent: dict[str, list[tuple[str, int]]] = {}
    for r in rows:
        by_parent.setdefault(r["parent"], []).append((r["leaf"], r["fact_count"]))
    report.metrics["parent_child"] = {
        p: {"leaves": len(leaves), "total_facts": sum(c for _, c in leaves)}
        for p, leaves in by_parent.items()
    }
    # Warn if a single leaf carries > 80% of a parent's facts
    for p, leaves in by_parent.items():
        if not leaves:
            continue
        total = sum(c for _, c in leaves)
        if total < 10:
            continue
        top_leaf, top_count = leaves[0]
        if top_count / total > 0.8:
            report.warn(
                f"under {p!r}: {top_leaf!r} carries "
                f"{top_count}/{total} ({top_count/total:.0%})"
            )
    return by_parent


def check_leaf_explosion(
    report: TreeValidationReport,
    *,
    max_thin_new_leaves: int = 5,
) -> int:
    """Count leaf topics with < 3 facts. Per directive, a sudden burst
    of zero/thin leaves usually means classifier drift."""
    with _conn() as c:
        rows = c.execute("""
            SELECT name FROM topics
             WHERE parent_topic_id IS NOT NULL
               AND fact_count < 3
        """).fetchall()
    thin = [r["name"] for r in rows]
    report.metrics["thin_leaves"] = len(thin)
    report.metrics["thin_leaf_names"] = thin
    if len(thin) > max_thin_new_leaves:
        report.warn(
            f"{len(thin)} thin leaves detected (cap {max_thin_new_leaves}); "
            f"sample: {thin[:5]}"
        )
    return len(thin)


def check_supersede_rate(
    report: TreeValidationReport,
    *,
    branch_topic: str | None,
    threshold: float = 0.80,
) -> float:
    """For Phase-1 reruns: % of facts in this branch's topic that got
    superseded during the most recent ingestion. > 80% = escalate (per
    directive section 11). Returns rate."""
    if not branch_topic:
        return 0.0
    with _conn() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM long_term_facts WHERE topic = ?",
            (branch_topic,),
        ).fetchone()[0]
        sup = c.execute(
            "SELECT COUNT(*) FROM long_term_facts "
            "WHERE topic = ? AND tags LIKE '%superseded%'",
            (branch_topic,),
        ).fetchone()[0]
    rate = (sup / total) if total else 0.0
    report.metrics[f"supersede_rate_{branch_topic}"] = round(rate, 4)
    if rate > threshold:
        report.fail(
            f"supersede rate {rate:.1%} for {branch_topic!r} exceeds "
            f"{threshold:.0%} — possible bad ingestion or wrong taxonomy"
        )
    return rate


def validate_after_branch(
    branch_or_config: str,
    *,
    new_facts_since: str | None = None,
    branch_topic: str | None = None,
) -> TreeValidationReport:
    """Run all checks. Returns a report; runner inspects report.passed
    and pauses to surface to John on any False.

    `new_facts_since` should be the ISO timestamp captured BEFORE this
    branch's ingestion started — so the new-uncategorized-rate metric
    measures only the just-ingested batch, not the entire DB.
    """
    report = TreeValidationReport(branch_or_config=branch_or_config)
    try:
        check_orphan_facts(report)
        check_uncategorized_rate(report, new_only_since=new_facts_since)
        check_parent_child_ratios(report)
        check_leaf_explosion(report)
        check_supersede_rate(report, branch_topic=branch_topic)
    except Exception as e:  # noqa: BLE001
        report.fail(f"validator crashed: {e}")
        log.exception("tree validation crashed")
    return report
