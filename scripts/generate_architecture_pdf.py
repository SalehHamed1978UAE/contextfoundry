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


def wrap_to_width(pdf, line: str, max_width: float) -> list[str]:
    """Wrap a line based on rendered width in the active PDF font."""
    if not line:
        return [""]
    words = line.split(" ")
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdf.get_string_width(candidate) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            # Hard-break a single oversized word
            if pdf.get_string_width(word) > max_width:
                chunk = ""
                for ch in word:
                    if pdf.get_string_width(chunk + ch) <= max_width:
                        chunk += ch
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                current = chunk
            else:
                current = word
    if current:
        lines.append(current)
    return lines


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
    # fpdf2 default fonts do not support box-drawing or other unicode glyphs.
    # Replace non-ASCII characters to avoid render errors.
    text = text.encode("ascii", "replace").decode("ascii")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    max_width = pdf.w - pdf.l_margin - pdf.r_margin
    for line in text.splitlines():
        for wrapped in wrap_to_width(pdf, line, max_width=max_width):
            if wrapped == "":
                pdf.ln(6)
                continue
            # Ensure cursor is at left margin before writing a line.
            pdf.set_x(pdf.l_margin)
            pdf.cell(max_width, 6, wrapped, ln=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    print(f"PDF written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
