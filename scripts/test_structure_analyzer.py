"""Verification harness for StructureAnalyzer (Component 1).

For each of the 5 target documents we print:
  1. Region map (type, line range, sample) — what the analyzer detected.
  2. Whether table rows are preserved as complete units (per-table line/cell
     counts, and whether each row is intact within ONE table region).
  3. Whether any markdown table row landed in a non-table region (split rows).

Pass criteria: ALL table rows in ALL 5 documents appear as complete, unsplit
regions. No row may land in a non-'table' region.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from context_foundry.discovery.structure_analyzer import (  # noqa: E402
    StructureAnalyzer,
    DocumentRegion,
)

DOCS = [
    ("test documents/ClaudeCode_NExus_Industries_corpus/communications/02_organizational_announcement.md", "leadership table"),
    ("test documents/ClaudeCode_NExus_Industries_corpus/technical/06_solid_state_battery_design.md", "spec tables"),
    ("test documents/ClaudeCode_NExus_Industries_corpus/financials/01_annual_report_2025.md", "financial tables"),
    ("test documents/ClaudeCode_NExus_Industries_corpus/projects/04_greenhydrogen_initiative.md", "mixed content"),
    ("test documents/ClaudeCode_NExus_Industries_corpus/strategy/10_board_strategic_priorities.md", "section headers"),
]


def _is_table_row(line: str) -> bool:
    """Stricter, format-aware check used only for the verification metric:
    a markdown table row starts and ends with '|' and has at least 2 '|'.
    This is what a downstream chunker MUST keep intact."""
    s = line.strip()
    return s.startswith('|') and s.endswith('|') and s.count('|') >= 2


def _row_signature(line: str) -> str:
    """Normalised signature for matching a row across before/after states."""
    return ' | '.join(c.strip() for c in line.strip().strip('|').split('|'))


def summarize_regions(regions: list[DocumentRegion]) -> dict:
    counts: dict[str, int] = {}
    for r in regions:
        counts[r.type] = counts.get(r.type, 0) + 1
    return counts


def verify_doc(path: Path, label: str) -> tuple[bool, list[str]]:
    """Returns (passed, error_messages)."""
    text = path.read_text(encoding='utf-8', errors='replace')
    raw_lines = text.split('\n')
    raw_table_rows = [(i, ln) for i, ln in enumerate(raw_lines) if _is_table_row(ln)]

    analyzer = StructureAnalyzer()
    regions = analyzer.analyze(text)

    print(f"\n{'=' * 78}")
    print(f"DOC: {path.name}  ({label})")
    print(f"{'=' * 78}")

    # 1. Region map
    summary = summarize_regions(regions)
    print(f"Region counts: {summary}")
    print(f"Total regions: {len(regions)}   Total lines: {len(raw_lines)}   "
          f"Markdown table rows in source: {len(raw_table_rows)}")

    # Print compact region map (first 40 regions).
    print("\nRegion map (first 40):")
    print(f"  {'#':>3} {'type':<8} {'lines':>10}  sample")
    for idx, r in enumerate(regions[:40]):
        sample = next((ln.strip() for ln in r.lines if ln.strip()), '')
        sample = (sample[:80] + '…') if len(sample) > 80 else sample
        print(f"  {idx:>3} {r.type:<8} {r.start_line}-{r.end_line:<6} {sample}")
    if len(regions) > 40:
        print(f"  … {len(regions) - 40} more")

    errors: list[str] = []

    # 2. Per-table region: verify rows are intact and unsplit
    table_regions = [r for r in regions if r.type == 'table']
    print(f"\nTable regions: {len(table_regions)}")
    rows_in_tables = 0
    for ti, tr in enumerate(table_regions):
        rows = [ln for ln in tr.lines if _is_table_row(ln)]
        rows_in_tables += len(rows)
        print(f"  table[{ti}] lines={tr.start_line}-{tr.end_line}  "
              f"line_count={tr.line_count}  rows={len(rows)}")
        if rows:
            print(f"    first row: {rows[0].strip()[:90]}")
            print(f"    last  row: {rows[-1].strip()[:90]}")

    # 3. Source-row coverage: every md table row in the source must appear,
    # verbatim and intact, inside SOME table region.
    region_signatures_by_table: list[set[str]] = [
        {_row_signature(ln) for ln in tr.lines if _is_table_row(ln)}
        for tr in table_regions
    ]
    missing_rows = []
    for src_idx, ln in raw_table_rows:
        sig = _row_signature(ln)
        if not any(sig in sigs for sigs in region_signatures_by_table):
            missing_rows.append((src_idx, ln.strip()[:90]))
    if missing_rows:
        errors.append(
            f"{len(missing_rows)} source markdown table row(s) NOT found intact "
            f"in any table region (split or misclassified)."
        )
        for src_idx, snippet in missing_rows[:5]:
            errors.append(f"   - L{src_idx}: {snippet}")

    # 4. Cross-check via analyzer's own diagnostic
    offenders = analyzer.find_split_table_rows(regions)
    if offenders:
        errors.append(
            f"{len(offenders)} table-shaped row(s) landed in non-'table' regions "
            f"per analyzer diagnostic."
        )
        for o in offenders[:5]:
            errors.append(f"   - L{o['line_index']} → {o['landed_in']}: "
                          f"{o['line'].strip()[:90]}")

    # 5. Row accounting
    print(f"\nRow accounting: {rows_in_tables} rows inside table regions "
          f"vs {len(raw_table_rows)} markdown rows in source.")

    if errors:
        print("\nFAIL:")
        for e in errors:
            print(f"  {e}")
        return False, errors
    else:
        print("\nPASS: all markdown table rows are preserved as complete, "
              "unsplit table regions.")
        return True, []


def main() -> int:
    overall_pass = True
    for rel, label in DOCS:
        path = ROOT / rel
        if not path.exists():
            print(f"\n!! MISSING DOC: {path}")
            overall_pass = False
            continue
        ok, _ = verify_doc(path, label)
        overall_pass = overall_pass and ok

    print(f"\n{'=' * 78}")
    print(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}")
    print(f"{'=' * 78}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
