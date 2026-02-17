"""
QuillBot AI Content Detector module.
Checks text and LaTeX papers for AI-generated content using QuillBot's API.
"""

import re
from typing import Optional

import click
import requests

BASE_URL = "https://quillbot.com"
SCORE_ENDPOINT = f"{BASE_URL}/api/ai-detector/score"
LANG_ENDPOINT = f"{BASE_URL}/api/utils/detect-language"
TEXT_UPPER_LIMIT = 30000
TEXT_LOWER_LIMIT = 3

HEADERS_BASE = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "namespace": "ai-detector",
    "platform-type": "webapp",
    "qb-product": "AI_CONTENT_DETECTOR",
    "webapp-version": "40.82.0",
    "origin": "https://quillbot.com",
    "referer": "https://quillbot.com/ai-content-detector",
}


def strip_latex(text: str) -> str:
    """Strip LaTeX commands and environments, keeping readable text."""
    # Remove comments
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)

    # Remove document class, usepackage, etc.
    text = re.sub(
        r"\\(documentclass|usepackage|newacronym|bibliographystyle)\b[^}]*\{[^}]*\}(\{[^}]*\})?",
        "",
        text,
    )
    text = re.sub(r"\\(label|ref|cite|eqref|pageref|footnote)\{[^}]*\}", "", text)

    # Remove begin/end document
    text = re.sub(r"\\begin\{document\}", "", text)
    text = re.sub(r"\\end\{document\}", "", text)

    # Remove figure/table environments but keep captions
    text = re.sub(r"\\begin\{(figure|table)\}\[?[^\]]*\]?", "", text)
    text = re.sub(r"\\end\{(figure|table)\}", "", text)
    text = re.sub(r"\\includegraphics[^}]*\{[^}]*\}", "", text)
    text = re.sub(r"\\centering", "", text)
    text = re.sub(r"\\resizebox\{[^}]*\}\{[^}]*\}\{", "", text)

    # Remove tabular environments
    text = re.sub(r"\\begin\{tabular\}\{[^}]*\}", "", text)
    text = re.sub(r"\\end\{tabular\}", "", text)
    text = re.sub(r"\\(toprule|midrule|bottomrule|hline)", "", text)
    text = re.sub(r"\\multirow\{[^}]*\}\{[^}]*\}", "", text)

    # Remove math environments but keep inline math text
    text = re.sub(r"\\\[.*?\\\]", "[formula]", text, flags=re.DOTALL)
    text = re.sub(
        r"\\begin\{(equation|align|gather)\*?\}.*?\\end\{(equation|align|gather)\*?\}",
        "[formula]",
        text,
        flags=re.DOTALL,
    )

    # Convert LaTeX formatting to plain text
    text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\textit\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\texttt\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\detokenize\{([^}]*)\}", r"\1", text)

    # Remove title, author, institute, etc.
    text = re.sub(
        r"\\(title|titlerunning|author|authorrunning|institute|email|maketitle|keywords)\b(\[[^\]]*\])?\{",
        "",
        text,
    )

    # Convert sections
    text = re.sub(r"\\section\*?\{([^}]*)\}", r"\n\n\1\n", text)
    text = re.sub(r"\\subsection\*?\{([^}]*)\}", r"\n\1\n", text)
    text = re.sub(r"\\subsubsection\*?\{([^}]*)\}", r"\n\1\n", text)

    # Convert lists
    text = re.sub(r"\\begin\{(itemize|enumerate)\}\[?[^\]]*\]?", "", text)
    text = re.sub(r"\\end\{(itemize|enumerate)\}", "", text)
    text = re.sub(r"\\item", "- ", text)

    # Remove caption command but keep text
    text = re.sub(r"\\caption\{([^}]*)\}", r"\1", text)

    # Remove bibliography
    text = re.sub(
        r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
        "",
        text,
        flags=re.DOTALL,
    )

    # Remove remaining LaTeX commands
    text = re.sub(r"\\(gls|Gls|acrshort|acrlong|acrfull)\{[^}]*\}", "LLMs", text)
    text = re.sub(
        r"\\(smallskip|medskip|bigskip|newline|newpage|clearpage|pagebreak)", "", text
    )
    text = re.sub(r"\\(inst|and)\{?\d*\}?", "", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)

    # Remove remaining braces
    text = re.sub(r"[{}]", "", text)

    # Clean up special characters
    text = text.replace("~", " ")
    text = text.replace("``", '"')
    text = text.replace("''", '"')
    text = text.replace("---", "\u2014")
    text = text.replace("--", "\u2013")
    text = text.replace("\\\\", "\n")
    text = text.replace("&", " ")

    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"^\s+$", "", text, flags=re.MULTILINE)

    return text.strip()


def extract_sections(tex_content: str) -> dict[str, str]:
    """Extract named sections from LaTeX content."""
    sections = {}
    pattern = r"\\section\*?\{([^}]*)\}(.*?)(?=\\section\*?\{|\\end\{document\}|$)"
    matches = re.finditer(pattern, tex_content, re.DOTALL)
    for m in matches:
        name = m.group(1).strip().lower()
        body = m.group(2).strip()
        sections[name] = strip_latex(body)

    # Also extract abstract
    abstract_match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex_content, re.DOTALL
    )
    if abstract_match:
        sections["abstract"] = strip_latex(abstract_match.group(1))

    return sections


def detect_language(text: str, token: str) -> tuple[str, str]:
    """Detect language of text using QuillBot API."""
    headers = {**HEADERS_BASE, "useridtoken": token}
    sample = text[:500]
    try:
        resp = requests.post(
            LANG_ENDPOINT, json={"text": sample}, headers=headers, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("language", "en"), data.get("languageName", "English")
    except Exception as e:
        click.echo(f"  Language detection failed ({e}), defaulting to English")
        return "en", "English"


def check_ai_score(
    text: str, token: str, language: str = "en", explain: bool = True
) -> dict:
    """Check text for AI content using QuillBot API."""
    if len(text) < TEXT_LOWER_LIMIT:
        return {"error": "Text too short (min 3 characters)"}
    if len(text) > TEXT_UPPER_LIMIT:
        click.echo(
            f"  Warning: Text exceeds {TEXT_UPPER_LIMIT} chars ({len(text)}), truncating..."
        )
        text = text[:TEXT_UPPER_LIMIT]

    headers = {**HEADERS_BASE, "useridtoken": token}
    body = {
        "text": text,
        "language": language,
        "explain": explain,
    }

    try:
        resp = requests.post(
            SCORE_ENDPOINT, json=body, headers=headers, timeout=120
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        body_text = e.response.text[:500] if e.response else ""
        return {"error": f"HTTP {status}: {body_text}", "status": status}
    except Exception as e:
        return {"error": str(e)}


def is_auth_error(result: dict) -> bool:
    """Check if a result indicates an expired/invalid token."""
    if "error" not in result:
        return False
    status = result.get("status")
    if status in (401, 403):
        return True
    error_msg = result["error"].lower()
    return "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg


def format_chunk_result(chunk: dict) -> str:
    """Format a single chunk result for display."""
    ctype = chunk.get("type", "UNKNOWN")
    score = chunk.get("aiScore", 0)
    confidence = chunk.get("confidence", "")
    text_preview = chunk.get("text", "")[:80].replace("\n", " ")

    if ctype == "AI":
        score_pct = int(score * 100) if score <= 1 else int(score)
        conf_str = f" ({confidence})" if confidence else ""
        categories = ""
        if chunk.get("explainer") and chunk["explainer"].get("categories"):
            categories = f" [{', '.join(chunk['explainer']['categories'])}]"
        return f'  AI {score_pct}%{conf_str}{categories}: "{text_preview}..."'
    elif ctype == "HUMAN-PARAPHRASED":
        return f'  PARAPHRASED: "{text_preview}..."'
    else:
        return f'  HUMAN: "{text_preview}..."'


def display_results(result: dict, label: str = "") -> Optional[dict]:
    """Display AI detection results."""
    if "error" in result:
        click.echo(click.style(f"\nError: {result['error']}", fg="red"))
        return None

    data = result.get("data", {}).get("value", result.get("data", result))

    if not data or (isinstance(data, dict) and data.get("timedOut")):
        click.echo(click.style("\nDetection timed out or returned empty data", fg="red"))
        return None

    ai_score = data.get("aiScore", data.get("totalAiScore", 0))
    if isinstance(ai_score, float) and ai_score <= 1:
        ai_score = int(ai_score * 100)
    human_score = 100 - ai_score
    model_ver = data.get("modelVersion", data.get("modelID", "unknown"))
    chunks = data.get("chunks", [])

    header = f" {label} " if label else " Results "
    click.echo(f"\n{'=' * 60}")
    click.echo(f"{header:=^60}")
    click.echo(f"{'=' * 60}")

    # Color the score based on severity
    if ai_score >= 50:
        score_color = "red"
    elif ai_score >= 20:
        score_color = "yellow"
    else:
        score_color = "green"

    click.echo(
        f"  Overall AI Score:    "
        + click.style(f"{ai_score}% AI", fg=score_color, bold=True)
        + f" / {human_score}% Human"
    )
    click.echo(f"  Model Version:       {model_ver}")
    click.echo(f"  Chunks Analyzed:     {len(chunks)}")

    ai_chunks = [c for c in chunks if c.get("type") == "AI"]
    human_chunks = [c for c in chunks if c.get("type") == "HUMAN"]
    paraphrased_chunks = [c for c in chunks if c.get("type") == "HUMAN-PARAPHRASED"]

    click.echo(f"  AI Chunks:           {len(ai_chunks)}")
    click.echo(f"  Human Chunks:        {len(human_chunks)}")
    click.echo(f"  Paraphrased Chunks:  {len(paraphrased_chunks)}")
    click.echo(f"{'─' * 60}")

    if ai_chunks:
        click.echo(click.style("\nAI-Detected Sections:", fg="red"))
        ai_sorted = sorted(
            ai_chunks, key=lambda c: c.get("aiScore", 0), reverse=True
        )
        for chunk in ai_sorted:
            click.echo(click.style(format_chunk_result(chunk), fg="red"))

    if paraphrased_chunks:
        click.echo(click.style("\nParaphrased Sections:", fg="yellow"))
        for chunk in paraphrased_chunks:
            click.echo(click.style(format_chunk_result(chunk), fg="yellow"))

    if human_chunks and len(human_chunks) <= 10:
        click.echo(click.style("\nHuman Sections:", fg="green"))
        for chunk in human_chunks:
            click.echo(click.style(format_chunk_result(chunk), fg="green"))
    elif human_chunks:
        click.echo(
            click.style(
                f"\n{len(human_chunks)} sections detected as human-written (omitted for brevity)",
                fg="green",
            )
        )

    click.echo(f"\n{'=' * 60}")

    return data
