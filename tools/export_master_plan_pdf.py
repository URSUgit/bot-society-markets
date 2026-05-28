"""Export the BITprivat master Markdown plan to a polished PDF.

The script intentionally avoids third-party Python packages so the artifact can
be regenerated on this Windows workstation with the local Microsoft Edge build.
It supports the Markdown features used by docs/33-bitprivat-master-rebuild-plan.md.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


EDGE_CANDIDATES = [
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "section"


def inline_markup(value: str, base_dir: Path) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)

    def link_repl(match: re.Match[str]) -> str:
        label = match.group(1)
        href = html.unescape(match.group(2))
        return f'<a href="{html.escape(href, quote=True)}">{label}</a>'

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, escaped)
    return escaped


def render_table(lines: list[str], base_dir: Path) -> str:
    rows = []
    for raw in lines:
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        rows.append(cells)
    header = rows[0]
    body = rows[2:]
    parts = ["<table>", "<thead><tr>"]
    for cell in header:
        parts.append(f"<th>{inline_markup(cell, base_dir)}</th>")
    parts.append("</tr></thead><tbody>")
    for row in body:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{inline_markup(cell, base_dir)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def render_markdown(markdown: str, source_path: Path) -> str:
    base_dir = source_path.parent
    lines = markdown.splitlines()
    output: list[str] = []
    i = 0
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    list_mode: str | None = None

    def close_list() -> None:
        nonlocal list_mode
        if list_mode:
            output.append(f"</{list_mode}>")
            list_mode = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if not in_code:
                close_list()
                in_code = True
                code_lang = stripped.strip("`").strip()
                code_lines = []
            else:
                css = "mermaid-code" if code_lang == "mermaid" else ""
                output.append(
                    f'<pre class="{css}"><code>{html.escape(chr(10).join(code_lines))}</code></pre>'
                )
                in_code = False
                code_lang = ""
                code_lines = []
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        if not stripped:
            close_list()
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            close_list()
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            output.append(render_table(table_lines, base_dir))
            continue

        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            close_list()
            alt = html.escape(image_match.group(1))
            image_ref = image_match.group(2)
            image_path = (base_dir / image_ref).resolve()
            output.append(
                f'<figure><img src="{image_path.as_uri()}" alt="{alt}"><figcaption>{alt}</figcaption></figure>'
            )
            i += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            close_list()
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            css = "cover-title" if level == 1 else ""
            output.append(
                f'<h{level} id="{slugify(text)}" class="{css}">{inline_markup(text, base_dir)}</h{level}>'
            )
            i += 1
            continue

        if stripped.startswith("- "):
            if list_mode != "ul":
                close_list()
                output.append("<ul>")
                list_mode = "ul"
            output.append(f"<li>{inline_markup(stripped[2:], base_dir)}</li>")
            i += 1
            continue

        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ordered_match:
            if list_mode != "ol":
                close_list()
                output.append("<ol>")
                list_mode = "ol"
            output.append(f"<li>{inline_markup(ordered_match.group(1), base_dir)}</li>")
            i += 1
            continue

        close_list()
        output.append(f"<p>{inline_markup(stripped, base_dir)}</p>")
        i += 1

    close_list()
    return "\n".join(output)


def build_html(markdown_path: Path) -> str:
    content = markdown_path.read_text(encoding="utf-8")
    body = render_markdown(content, markdown_path)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>BITprivat Master Rebuild and Commercialization Plan</title>
  <style>
    @page {{ size: A4; margin: 16mm 14mm 18mm 14mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
      font-size: 10.5pt;
      line-height: 1.5;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      background:
        radial-gradient(circle at 10% 0%, rgba(37, 99, 235, .12), transparent 30%),
        radial-gradient(circle at 90% 10%, rgba(15, 118, 110, .12), transparent 28%);
      z-index: -1;
    }}
    h1, h2, h3 {{ line-height: 1.14; page-break-after: avoid; }}
    h1 {{
      margin: 0 0 8mm;
      padding: 18mm 16mm;
      color: white;
      background: linear-gradient(135deg, #0f172a, #0f766e 55%, #2563eb);
      border-radius: 20px;
      font-size: 30pt;
      letter-spacing: -0.03em;
      box-shadow: 0 16px 40px rgba(15, 23, 42, .18);
    }}
    h2 {{
      margin: 11mm 0 4mm;
      padding-top: 3mm;
      border-top: 1px solid #cbd5e1;
      color: #0f172a;
      font-size: 18pt;
    }}
    h3 {{
      margin: 7mm 0 3mm;
      color: #0f766e;
      font-size: 13.5pt;
    }}
    p {{ margin: 0 0 3.8mm; }}
    a {{ color: #2563eb; text-decoration: none; }}
    code {{
      font-family: "Cascadia Mono", Consolas, monospace;
      background: #e2e8f0;
      border-radius: 4px;
      padding: 0 3px;
      font-size: 9.2pt;
    }}
    pre {{
      white-space: pre-wrap;
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 14px;
      padding: 12px 14px;
      font-size: 8.3pt;
      page-break-inside: avoid;
    }}
    pre.mermaid-code {{
      background: #ecfeff;
      color: #164e63;
      border: 1px solid #a5f3fc;
    }}
    ul, ol {{ margin: 0 0 4mm 5mm; padding-left: 5mm; }}
    li {{ margin: 1.4mm 0; }}
    table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      margin: 4mm 0 6mm;
      overflow: hidden;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      background: white;
      page-break-inside: avoid;
    }}
    th {{
      background: #eaf2ff;
      color: #0f172a;
      text-align: left;
      font-weight: 800;
      padding: 7px 8px;
      border-bottom: 1px solid #cbd5e1;
    }}
    td {{
      padding: 7px 8px;
      vertical-align: top;
      border-bottom: 1px solid #e2e8f0;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    tr:nth-child(even) td {{ background: #f8fafc; }}
    figure {{
      margin: 5mm 0 7mm;
      padding: 5mm;
      background: white;
      border: 1px solid #cbd5e1;
      border-radius: 18px;
      page-break-inside: avoid;
      box-shadow: 0 12px 28px rgba(15, 23, 42, .08);
    }}
    img {{ width: 100%; height: auto; display: block; }}
    figcaption {{
      margin-top: 3mm;
      color: #475569;
      font-size: 8.7pt;
      font-weight: 700;
    }}
    strong {{ font-weight: 850; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def find_edge() -> str:
    for candidate in EDGE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in ("msedge", "microsoft-edge", "chrome", "chromium"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise RuntimeError("Microsoft Edge or another Chromium browser was not found.")


def export_pdf(markdown_path: Path, pdf_path: Path, keep_html: bool = False) -> Path:
    markdown_path = markdown_path.resolve()
    pdf_path = pdf_path.resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = build_html(markdown_path)
    if keep_html:
        html_path = pdf_path.with_suffix(".html")
        html_path.write_text(html_content, encoding="utf-8")
    else:
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False)
        temp.write(html_content)
        temp.close()
        html_path = Path(temp.name)

    try:
        edge = find_edge()
        command = [
            edge,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={str(pdf_path)}",
            html_path.resolve().as_uri(),
        ]
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    finally:
        if not keep_html:
            try:
                html_path.unlink()
            except OSError:
                pass

    for _ in range(40):
        if pdf_path.exists() and pdf_path.stat().st_size >= 10_000:
            break
        time.sleep(0.25)

    if not pdf_path.exists() or pdf_path.stat().st_size < 10_000:
        raise RuntimeError(f"PDF export failed or produced an unexpectedly small file: {pdf_path}")
    return pdf_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the BITprivat master rebuild plan to PDF.")
    parser.add_argument(
        "--input",
        default="docs/33-bitprivat-master-rebuild-plan.md",
        help="Markdown plan path.",
    )
    parser.add_argument(
        "--output",
        default="docs/33-bitprivat-master-rebuild-plan.pdf",
        help="PDF output path.",
    )
    parser.add_argument("--keep-html", action="store_true", help="Keep an HTML sibling for debugging.")
    args = parser.parse_args()

    try:
        pdf = export_pdf(Path(args.input), Path(args.output), keep_html=args.keep_html)
    except Exception as exc:  # pragma: no cover - operator script
        print(f"PDF export failed: {exc}", file=sys.stderr)
        return 1
    print(f"Exported {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
