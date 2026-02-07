#!/usr/bin/env python3
"""
Generate a PDF from docs/architecture_summary.md using fpdf2.

Usage:
  python scripts/generate_architecture_pdf.py
  python scripts/generate_architecture_pdf.py --input docs/architecture_summary.md --output docs/architecture_summary.pdf
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def strip_markdown(text: str) -> str:
    """Lightweight markdown-to-text conversion for PDF output."""
    # Remove fenced code markers but keep content
    text = re.sub(r"```[a-zA-Z0-9_-]*\n", "", text)
    text = text.replace("```", "")

    # Headings: remove leading hashes
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Bold/italic markers
    text = text.replace("**", "").replace("__", "")
    text = text.replace("*", "")

    # Bullet normalization
    text = re.sub(r"^-\s+", "• ", text, flags=re.MULTILINE)

    return text


def hard_wrap_long_tokens(line: str, max_len: int = 100) -> list[str]:
    """
    Break lines that contain very long tokens (e.g., separators or long code)
    so fpdf2 can render them without throwing width errors.
    """
    if len(line) <= max_len:
        return [line]

    # If there are no spaces, hard-wrap the line.
    if " " not in line:
        return [line[i:i + max_len] for i in range(0, len(line), max_len)]

    # Otherwise, wrap by words.
    parts = []
    current = []
    current_len = 0
    for word in line.split():
        word_len = len(word)
        if current_len + word_len + (1 if current else 0) > max_len:
            parts.append(" ".join(current))
            current = [word]
            current_len = word_len
        else:
            current.append(word)
            current_len += word_len + (1 if current_len else 0)
    if current:
        parts.append(" ".join(current))
    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PDF from architecture_summary.md")
    parser.add_argument(
        "--input",
        default="docs/architecture_summary.md",
        help="Path to input markdown file",
    )
    parser.add_argument(
        "--output",
        default="docs/architecture_summary.pdf",
        help="Path to output PDF file",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"ERROR: Input not found: {input_path}", file=sys.stderr)
        return 1

    try:
        from fpdf import FPDF  # fpdf2
    except Exception:
        print(
            "ERROR: fpdf2 is not installed. Install with: pip install fpdf2",
            file=sys.stderr,
        )
        return 1

    raw = input_path.read_text(encoding="utf-8")
    text = strip_markdown(raw)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    for line in text.splitlines():
        for wrapped in hard_wrap_long_tokens(line, max_len=100):
            pdf.multi_cell(0, 6, wrapped)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    print(f"PDF written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
