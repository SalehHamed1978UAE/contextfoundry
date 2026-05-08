"""StructureAnalyzer — Component 1 of the Intelligent Auto-Discovery System.

Classifies document regions (prose, table, list, header, code, blank) using
statistical/structural properties of each line, not hardcoded format regexes.

The integration target: the chunker consults the region map and never splits a
single table region across chunks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DocumentRegion:
    type: str  # 'prose' | 'table' | 'list' | 'header' | 'code' | 'blank'
    start_line: int
    end_line: int = -1
    lines: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def line_count(self) -> int:
        return len(self.lines)


class StructureAnalyzer:
    """Analyze document structure without hardcoded format patterns.

    The classifier inspects each line's structural properties and the local
    neighborhood (a few lines before/after). It is deliberately format-agnostic:
    it doesn't look for the word 'markdown' or trigger on a leading '|' alone —
    it asks whether *the surrounding text consistently behaves as a table*.
    """

    # Heuristic constants. Kept conservative so we err on the side of
    # NOT classifying a single decorative '|' line as a table.
    _PIPE_DENSITY_MIN = 0.05  # share of '|' chars in stripped line
    _PIPE_COUNT_MIN = 2       # at least 2 column separators
    _NEIGHBOR_WINDOW = 2      # how many lines on either side to inspect
    _NEIGHBOR_AGREE_MIN = 1   # how many neighbors must also look table-like
    _HEADER_MAX_LEN = 120

    _LIST_RE = re.compile(r'^\s*([\*\-\u2022\+]|\d+[\.\)])\s+\S')
    _MD_HEADER_RE = re.compile(r'^\s*#{1,6}\s+\S')
    _SETEXT_UNDERLINE_RE = re.compile(r'^\s*([=\-]){3,}\s*$')
    _CODE_FENCE_RE = re.compile(r'^\s*```')

    def analyze(self, raw_text: str) -> List[DocumentRegion]:
        """Return an ordered list of contiguous, typed regions."""
        if not raw_text:
            return []

        lines = raw_text.split('\n')
        # Pre-compute a row-level "table-ness" signal so we can use a small
        # neighborhood for context-sensitive classification of edge rows
        # (header separator '|---|---|', single rows, etc.).
        row_table_signal = [self._row_looks_like_table(ln) for ln in lines]

        # Track an explicit code-fence state — fences mark regions verbatim.
        in_fence = False

        types: List[str] = [''] * len(lines)
        for i, line in enumerate(lines):
            if self._CODE_FENCE_RE.match(line):
                # The fence line itself is part of the code region; flip state.
                types[i] = 'code'
                in_fence = not in_fence
                continue
            if in_fence:
                types[i] = 'code'
                continue
            types[i] = self._classify_line(line, i, lines, row_table_signal)

        # Setext-style headers: a non-empty line followed by ===/--- becomes
        # a header (and the underline is folded into it).
        for i in range(len(lines) - 1):
            if (
                types[i] in ('prose', 'header')
                and lines[i].strip()
                and self._SETEXT_UNDERLINE_RE.match(lines[i + 1])
                and types[i + 1] != 'table'  # don't mis-promote a md table header sep
            ):
                types[i] = 'header'
                types[i + 1] = 'header'

        # Build regions from the type stream.
        regions: List[DocumentRegion] = []
        cur: Optional[DocumentRegion] = None
        for i, line in enumerate(lines):
            t = types[i]
            if cur is None or cur.type != t:
                if cur is not None:
                    cur.end_line = i - 1
                    regions.append(cur)
                cur = DocumentRegion(type=t, start_line=i, lines=[])
            cur.lines.append(line)
        if cur is not None:
            cur.end_line = len(lines) - 1
            regions.append(cur)

        regions = self._post_process(regions)
        return regions

    # ------------------------------------------------------------------ classify
    def _row_looks_like_table(self, line: str) -> bool:
        """Cheap, line-local check used as a neighborhood signal.

        A line "looks like a table row" if it has multiple '|' separators
        AND the pipes constitute a meaningful share of the content
        (filtering out incidental pipes inside prose).
        """
        s = line.strip()
        if not s:
            return False
        n = s.count('|')
        if n < self._PIPE_COUNT_MIN:
            return False
        # Strongest structural signal: the line is bracketed by '|' on both
        # ends. That shape is a table row regardless of cell verbosity, so
        # density is irrelevant here. (Long rows like
        # "| Fossil Fuel Displaced | 15 million gallons diesel equivalent |"
        # are below typical density thresholds but are unambiguously rows.)
        if s.startswith('|') and s.endswith('|'):
            return True
        # Fallback: not bracketed → require pipe density to defend against
        # incidental '|' usage inside prose.
        density = n / max(len(s), 1)
        return density >= self._PIPE_DENSITY_MIN

    def _classify_line(
        self,
        line: str,
        index: int,
        all_lines: List[str],
        row_table_signal: List[bool],
    ) -> str:
        stripped = line.strip()

        if not stripped:
            return 'blank'

        # Markdown ATX header
        if self._MD_HEADER_RE.match(line):
            return 'header'

        # Table: this line looks like a row AND at least one neighbor agrees.
        if row_table_signal[index]:
            lo = max(0, index - self._NEIGHBOR_WINDOW)
            hi = min(len(all_lines), index + self._NEIGHBOR_WINDOW + 1)
            agree = sum(
                1 for j in range(lo, hi)
                if j != index and row_table_signal[j]
            )
            if agree >= self._NEIGHBOR_AGREE_MIN:
                return 'table'

        # List item
        if self._LIST_RE.match(line):
            return 'list'

        # Code by indentation + code-ish chars (loose; fenced code already handled)
        if (line.startswith('    ') or line.startswith('\t')) and any(
            c in stripped for c in '{};='
        ):
            return 'code'

        # Header by shape: short, non-sentence-ending, followed by blank/different.
        # Used for plain-text/setext-ish docs where ATX headers aren't used.
        if len(stripped) <= self._HEADER_MAX_LEN and not stripped.endswith(('.', ',', ';', ':')):
            next_blank = (
                index + 1 < len(all_lines)
                and all_lines[index + 1].strip() == ''
            )
            # Avoid over-promoting normal short prose lines: require that the
            # NEXT non-blank line is either blank-terminated or a list/header,
            # which is the typical layout signal for a heading.
            if next_blank and not self._looks_like_sentence_fragment(stripped):
                return 'header'

        return 'prose'

    @staticmethod
    def _looks_like_sentence_fragment(s: str) -> bool:
        # Cheap check: lots of lowercase function words → probably prose, not header.
        words = s.split()
        if len(words) < 4:
            return False
        common = sum(1 for w in words if w.lower() in {
            'the', 'a', 'an', 'and', 'or', 'but', 'of', 'in', 'on', 'to',
            'for', 'with', 'by', 'is', 'are', 'was', 'were', 'has', 'have',
            'this', 'that', 'these', 'those', 'it', 'its',
        })
        return common / len(words) > 0.25

    # ------------------------------------------------------------------ post
    def _post_process(self, regions: List[DocumentRegion]) -> List[DocumentRegion]:
        """Merge adjacent same-type regions and absorb single blank lines that
        sit *inside* a table block (rare but happens with some exporters)."""
        if not regions:
            return regions

        # Pass 1: heal table interruptions caused by a single blank line whose
        # prev AND next are tables. Reclassify the blank gap as table so it
        # gets merged.
        for i in range(1, len(regions) - 1):
            if (
                regions[i].type == 'blank'
                and regions[i].line_count == 1
                and regions[i - 1].type == 'table'
                and regions[i + 1].type == 'table'
            ):
                regions[i].type = 'table'

        # Pass 2: merge adjacent same-type
        merged: List[DocumentRegion] = []
        for r in regions:
            if merged and merged[-1].type == r.type:
                merged[-1].lines.extend(r.lines)
                merged[-1].end_line = r.end_line
            else:
                merged.append(r)
        return merged

    # ------------------------------------------------------------------ utility
    def find_split_table_rows(self, regions: List[DocumentRegion]) -> List[dict]:
        """Diagnostic: report any line that *looks like a table row* but
        landed in a non-'table' region. Used by the verification harness.

        A "table row" here is the same neighborhood-aware criterion the
        classifier uses, so this answers: did a row that should be table
        actually escape into prose/list/header/code?
        """
        all_lines: List[str] = []
        line_to_region: List[DocumentRegion] = []
        for r in regions:
            for ln in r.lines:
                all_lines.append(ln)
                line_to_region.append(r)
        signal = [self._row_looks_like_table(ln) for ln in all_lines]
        offenders: List[dict] = []
        for i, ln in enumerate(all_lines):
            if not signal[i]:
                continue
            # Only flag if a neighbor also looks like a row — otherwise this
            # is an isolated pipe-bearing prose line, not a real table row.
            lo = max(0, i - self._NEIGHBOR_WINDOW)
            hi = min(len(all_lines), i + self._NEIGHBOR_WINDOW + 1)
            agree = sum(1 for j in range(lo, hi) if j != i and signal[j])
            if agree < self._NEIGHBOR_AGREE_MIN:
                continue
            r = line_to_region[i]
            if r.type != 'table':
                offenders.append({
                    'line_index': i,
                    'line': ln,
                    'landed_in': r.type,
                    'region_start_line': r.start_line,
                })
        return offenders
