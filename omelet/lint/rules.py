"""The rules.

Two families, and they are not the same job:

SLOP-* and VOICE-* catch the tells of machine-written prose - the em-dash rash,
the marketing filler, the "Statement. Statement. Statement." rhythm, the polite
CTA at the end. These are cheap to detect and a false positive costs you five
seconds.

DEPTH-* is the harder half, and it is honest about what it can and cannot see.
No regex knows whether a thesis is true. What a regex *can* see is whether a
number was asserted with nothing behind it, whether the post leans on secondary
sources, and whether the author produced anything a reader could not have got by
reading the same headlines. Those are proxies for depth, not depth itself. The
judgment half lives in the post's spec.json.

Every rule carries a `fix` line. A finding that does not teach the fix just
trains you to ignore the linter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterator
from urllib.parse import urlparse

from .doc import Doc

Severity = str  # "error" | "warn" | "info"


@dataclass
class Finding:
    rule: str
    severity: Severity
    line: int
    col: int
    message: str
    fix: str


@dataclass
class Options:
    min_citations: int = 8
    min_primary_ratio: float = 0.5
    longform_words: int = 1200
    max_short_run: int = 4  # consecutive short sentences before it reads as AI
    short_sentence_words: int = 12


RULES: list[tuple[str, Severity, Callable]] = []


def rule(rid: str, severity: Severity):
    def deco(fn):
        RULES.append((rid, severity, fn))
        return fn

    return deco


# --------------------------------------------------------------------------
# SLOP: the tells of machine-written prose
# --------------------------------------------------------------------------

_NON_ASCII_PUNCT = {
    "—": ("em-dash", "-"),
    "–": ("en-dash", "-"),
    "“": ("smart quote", '"'),
    "”": ("smart quote", '"'),
    "‘": ("smart quote", "'"),
    "’": ("smart quote", "'"),
}


@rule("SLOP-P1", "error")
def ascii_punctuation(doc: Doc, opt: Options) -> Iterator[tuple[int, str, str]]:
    """Em-dash and smart quotes. The single loudest AI tell in 2026 prose."""
    for i, ch in enumerate(doc.masked):
        if ch in _NON_ASCII_PUNCT:
            name, repl = _NON_ASCII_PUNCT[ch]
            yield i, f"{name} {ch} - bài viết chỉ dùng dấu câu ASCII", f"thay bằng {repl}"


_CLICHE_HARD = [
    "giá trị cốt lõi", "trải nghiệm tuyệt vời", "trải nghiệm liền mạch",
    "chất lượng hàng đầu", "đẳng cấp quốc tế", "giải pháp toàn diện",
    "cách mạng hoá", "cách mạng hóa", "thay đổi cuộc chơi",
    "hy vọng bài viết hữu ích", "hi vọng bài viết hữu ích",
    "chúc bạn một ngày tốt lành", "thời đại 4.0", "công nghệ 4.0",
    "kỷ nguyên số", "chuyển đổi số toàn diện", "đồng hành cùng",
    "mang lại giá trị", "tận tâm", "cam kết mang đến",
]

_CLICHE_SOFT = ["hành trình", "đột phá", "hệ sinh thái", "cộng đồng"]


@rule("SLOP-P2", "error")
def marketing_cliche(doc: Doc, opt: Options):
    """Phrases that are worn through. They say nothing, which is why they are easy to type."""
    low = doc.masked.lower()
    for phrase in _CLICHE_HARD:
        for m in re.finditer(re.escape(phrase), low):
            yield m.start(), f'cụm marketing rỗng: "{phrase}"', (
                "viết cụ thể điều đã xảy ra, đừng gọi tên cảm xúc về nó"
            )


@rule("SLOP-P2S", "warn")
def marketing_cliche_soft(doc: Doc, opt: Options):
    """Words that are fine as technical terms and hollow as filler. Judgment needed."""
    low = doc.masked.lower()
    for phrase in _CLICHE_SOFT:
        for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", low):
            yield m.start(), f'từ dễ rỗng: "{phrase}"', (
                "giữ lại nếu đang dùng đúng nghĩa kỹ thuật; bỏ nếu chỉ là filler"
            )


_AI_CLOSING = [
    r"\btóm lại\b", r"\btổng kết lại\b", r"\bhy vọng\b.{0,40}\bhữu ích\b",
    r"\bhi vọng\b.{0,40}\bhữu ích\b", r"\bchúc các bạn\b", r"\bchúc bạn\b.{0,30}\bvui vẻ\b",
    r"\btrên đây là\b", r"\bqua bài viết này\b", r"\bnhư vậy\b,?\s*(chúng ta|ta)\s*đã\b",
]
_AI_CLOSING_HEADING = re.compile(r"^#{1,6}\s*(kết luận|tổng kết|lời kết)\s*$", re.I | re.M)


@rule("SLOP-P3", "error")
def ai_closing(doc: Doc, opt: Options):
    """The polite wrap-up. Bình voice ends on a quiet resolution or an open question."""
    tail_start = int(len(doc.masked) * 0.65)
    tail = doc.masked[tail_start:]
    for pat in _AI_CLOSING:
        for m in re.finditer(pat, tail, re.I):
            yield tail_start + m.start(), (
                f'kết bài kiểu AI: "{m.group(0).strip()}"'
            ), "kết bằng suy tư để ngỏ, câu hỏi mở, hoặc một moment đóng vòng"
    for m in _AI_CLOSING_HEADING.finditer(doc.masked):
        yield m.start(), f'heading tổng kết: "{m.group(0).strip()}"', (
            "bỏ heading; nếu cần đóng bài thì đóng bằng nội dung, không bằng nhãn"
        )


_GENERIC_OPENING = [
    r"trong thời đại", r"ngày nay", r"như chúng ta đã biết", r"không thể phủ nhận",
    r"trong bài viết này,?\s*(chúng ta|mình|tôi)?\s*sẽ", r"bạn có biết rằng",
    r"trong những năm gần đây", r"với sự phát triển (vượt bậc|nhanh chóng)",
]


@rule("SLOP-P4", "error")
def generic_opening(doc: Doc, opt: Options):
    """The first two paragraphs decide whether the post sounds like a person."""
    prose = doc.prose_blocks[:2]
    for b in prose:
        for pat in _GENERIC_OPENING:
            for m in re.finditer(pat, b.text, re.I):
                yield b.start + m.start(), (
                    f'mở bài generic: "{m.group(0).strip()}"'
                ), "mở bằng một moment cụ thể, một confession, hoặc câu hỏi bạn tự hỏi"


_AI_TRANSITIONS = [
    r"\bhơn nữa\b", r"\bngoài ra\b", r"\bbên cạnh đó\b", r"\bđiều đáng chú ý là\b",
    r"\btuy nhiên,\s*cần lưu ý\b", r"\bcó thể nói rằng\b", r"\bđáng chú ý hơn\b",
]


@rule("SLOP-P5", "warn")
def ai_transitions(doc: Doc, opt: Options):
    """Connective tissue that connects nothing. Fires only when the density is real."""
    hits = []
    for pat in _AI_TRANSITIONS:
        hits += [m.start() for m in re.finditer(pat, doc.masked, re.I)]
    budget = max(2, doc.word_count // 800)
    if len(hits) > budget:
        for i in sorted(hits)[budget:]:
            yield i, (
                f"transition rỗng (bài có {len(hits)}, ngưỡng {budget})"
            ), "nối ý bằng lập luận, không bằng từ nối; hoặc bỏ hẳn câu"


@rule("SLOP-P6", "warn")
def choppy_rhythm(doc: Doc, opt: Options):
    """A run of short standalone sentences. One is rhythm; four in a row is a machine."""
    for b in doc.prose_blocks:
        run = 0
        run_start = b.start
        pos = 0
        for s in doc.sentences(b):
            idx = b.text.find(s, pos)
            pos = idx + len(s) if idx >= 0 else pos
            if len(s.split()) <= opt.short_sentence_words:
                if run == 0:
                    run_start = b.start + max(idx, 0)
                run += 1
            else:
                run = 0
        if run >= opt.max_short_run:
            yield run_start, (
                f"{run} câu ngắn liên tiếp - nhịp 'Statement. Statement. Statement.'"
            ), "nối lại thành câu dài có nhịp; giữ câu ngắn đứng riêng chỉ khi nó là khoảng lặng có chủ ý"


_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)


@rule("SLOP-P7", "error")
def no_emoji(doc: Doc, opt: Options):
    for m in _EMOJI.finditer(doc.masked):
        yield m.start(), f"emoji trong bài viết: {m.group(0)}", "bỏ emoji"


_LISTICLE_TITLE = re.compile(
    r"^\s*(top\s*\d+|\d+\s*(cách|thuật toán|lý do|bước|công cụ|mẹo|tips|điều|thứ)\b)", re.I
)


@rule("SLOP-P8", "warn")
def listicle_title(doc: Doc, opt: Options):
    title = str(doc.frontmatter.get("title", ""))
    if _LISTICLE_TITLE.match(title):
        yield 0, f'title kiểu listicle: "{title}"', (
            "listicle chỉ được phép khi mỗi item là một investigation riêng; nếu không, đổi title"
        )


_HEDGES = [r"\bcó lẽ\b", r"\bcó thể nói\b", r"\btheo một số ý kiến\b",
           r"\bnhìn chung\b", r"\bphần nào đó\b", r"\btương đối là\b"]


@rule("SLOP-P9", "warn")
def hedging(doc: Doc, opt: Options):
    hits = []
    for pat in _HEDGES:
        hits += [m.start() for m in re.finditer(pat, doc.masked, re.I)]
    budget = max(1, doc.word_count // 900)
    if len(hits) > budget:
        for i in sorted(hits)[budget:]:
            yield i, f"hedging (bài có {len(hits)}, ngưỡng {budget})", (
                "commit vào luận điểm, hoặc ghi rõ confidence level thay vì làm mờ câu"
            )


@rule("SLOP-P10", "warn")
def bullet_heavy(doc: Doc, opt: Options):
    """A post that is mostly bullets is a report, not an essay."""
    if doc.word_count < 400:
        return
    bullet_words = sum(b.words for b in doc.blocks if b.kind == "list")
    total = bullet_words + doc.word_count
    if total and bullet_words / total > 0.35:
        pct = int(100 * bullet_words / total)
        yield 0, f"{pct}% chữ nằm trong bullet - bài đọc như báo cáo", (
            "chuyển bullet thành đoạn văn có lập luận; giữ bullet cho thứ thật sự là danh sách"
        )


# --------------------------------------------------------------------------
# DEPTH: proxies for whether the work was actually done
# --------------------------------------------------------------------------

# Một con số kèm đơn vị là một claim. "802.1X" thì không: đó là tên chuẩn IEEE, và
# lookbehind (?<![\w.]) chặn đúng chỗ đó - nếu không, "1X" trong "802.1X" sẽ bị đọc
# thành "1 lần". Một linter kêu oan là một linter bị tắt.
_NUM = r"(?<![\w.,])\d+(?:[.,]\d+)?"
_UNITS = (
    r"%|tỷ|tỉ|triệu|nghìn|usd|đô|đồng|vnd|lần|ms|gb|mb|"
    r"giây|phút|tiếng|điểm|người|user|request|token"
)
_CLAIM_NUMBER = re.compile(
    rf"{_NUM}\s?(?:{_UNITS})\b|(?<![\w.])\d+x\b",
    re.I,
)


@rule("DEPTH-D1", "warn")
def unsourced_number(doc: Doc, opt: Options):
    """A number with nothing behind it is an opinion wearing a lab coat."""
    for b in doc.prose_blocks:
        if doc.has_source(b.text):
            continue
        m = _CLAIM_NUMBER.search(b.text)
        if m:
            yield b.start + m.start(), (
                f'số liệu không có nguồn: "{m.group(0).strip()}"'
            ), "thêm [@key] / <Cite> / link primary source vào đoạn này, hoặc bỏ con số"


@rule("DEPTH-D2", "warn")
def citation_thin(doc: Doc, opt: Options):
    if doc.word_count < opt.longform_words:
        return
    n = len(doc.used_keys)
    if n < opt.min_citations:
        yield 0, (
            f"bài {doc.word_count} chữ nhưng chỉ có {n} citation (ngưỡng {opt.min_citations})"
        ), "đào thêm primary source, hoặc cắt những claim không chống lưng được"


@rule("DEPTH-D3", "error")
def citation_dead(doc: Doc, opt: Options):
    if not doc.citations:
        if doc.used_keys:
            yield 0, (
                f"bài dùng {len(doc.used_keys)} citation key nhưng không có citations.yaml"
            ), "tạo citations.yaml trong folder bài viết"
        return
    from .doc import CITE_KEY_RE

    for m in CITE_KEY_RE.finditer(doc.masked):
        key = m.group(1)
        if key not in doc.citations:
            import difflib

            near = difflib.get_close_matches(key, list(doc.citations), n=1)
            hint = f" (ý bạn là '{near[0]}'?)" if near else ""
            yield m.start(), f"citation key không tồn tại: [@{key}]{hint}", (
                "sửa key hoặc thêm entry vào citations.yaml"
            )


_PRIMARY_HOSTS = (
    "arxiv.org", "sec.gov", "github.com", "ietf.org", "rfc-editor.org",
    "python.org", "kernel.org", "acm.org", "ieee.org", "usenix.org",
    "openreview.net", "nist.gov", "cve.org", "mitre.org", "nvd.nist.gov",
    "sbv.gov.vn", "gso.gov.vn", "chinhphu.vn", "openai.com", "anthropic.com",
    "googleblog.com", "research.google", "meta.com", "nvidia.com",
)
_PRIMARY_TYPES = {"paper", "filing", "spec", "doc", "docs", "code", "data",
                  "primary", "law", "report", "transcript"}


def _is_primary(entry: dict) -> bool:
    if str(entry.get("type", "")).lower() in _PRIMARY_TYPES:
        return True
    host = urlparse(str(entry.get("url", ""))).netloc.lower()
    return any(host == h or host.endswith("." + h) or host.endswith(h)
               for h in _PRIMARY_HOSTS)


@rule("DEPTH-D4", "warn")
def primary_source_ratio(doc: Doc, opt: Options):
    used = [k for k in doc.used_keys if k in doc.citations]
    if len(used) < 4:
        return
    primary = [k for k in used if _is_primary(doc.citations[k])]
    ratio = len(primary) / len(used)
    if ratio < opt.min_primary_ratio:
        yield 0, (
            f"chỉ {len(primary)}/{len(used)} citation là primary source "
            f"({int(ratio * 100)}%, ngưỡng {int(opt.min_primary_ratio * 100)}%)"
        ), "thay blog post / bài báo tổng hợp bằng filing, paper, RFC, source code, official docs"


_ORIGINAL_MARKERS = re.compile(
    r"<Evidence\b|<Scenario\b|```(?:python|bash|sh|sql|rust|go|js|ts)\b", re.I
)


@rule("DEPTH-D5", "warn")
def no_original_artifact(doc: Doc, opt: Options):
    """Did the author make anything, or just rearrange what was already online?"""
    if doc.word_count < opt.longform_words:
        return
    if doc.local_images or _ORIGINAL_MARKERS.search(doc.body):
        return
    yield 0, "bài không có artifact gốc nào (không hình tự tạo, không code chạy được, không <Evidence>)", (
        "thêm một thứ người khác không copy được: benchmark tự chạy, screenshot primary source, "
        "biểu đồ tự vẽ, phép tính tự làm"
    )


_STEELMAN = re.compile(
    r"<Objection\b|phía (bênh|ủng hộ|phản đối)|counter-?argument|fair point|"
    r"lập luận ngược lại|người không đồng ý|phản biện lại",
    re.I,
)


@rule("DEPTH-D6", "warn")
def no_steelman(doc: Doc, opt: Options):
    if doc.word_count < 1500:
        return
    shape = str(doc.frontmatter.get("shape", "")).lower()
    if shape and shape not in ("investigation", "argument"):
        return
    if _STEELMAN.search(doc.body):
        return
    yield 0, "bài dài nhưng không steel-man phía đối lập", (
        "trình bày lập luận ngược ở dạng MẠNH NHẤT rồi mới phản biện; dùng <Objection> nếu tiện"
    )


# --------------------------------------------------------------------------
# VOICE
# --------------------------------------------------------------------------


@rule("VOICE-V1", "warn")
def signature(doc: Doc, opt: Options):
    if doc.word_count < opt.longform_words:
        return
    tail = doc.masked[-400:]
    if re.search(r"(?m)^\s*(-{2,}\s*)?Bình\s*$", tail) or re.search(r"\bBình\b\s*$", tail.strip()):
        return
    yield max(len(doc.masked) - 1, 0), "bài dài không ký tên 'Bình'", (
        "ký 'Bình' ở cuối bài - cá nhân gánh trách nhiệm cá nhân"
    )


@rule("VOICE-V2", "warn")
def person_drift(doc: Doc, opt: Options):
    if doc.word_count < 600:
        return
    minh = len(re.findall(r"\bmình\b", doc.masked, re.I))
    toi = len(re.findall(r"\btôi\b", doc.masked, re.I))
    if minh == 0 and toi > 0:
        yield 0, f'bài xưng "tôi" ({toi} lần), không có "mình"', (
            'giọng Bình xưng "mình", gọi "bạn"'
        )
    elif minh == 0 and toi == 0:
        yield 0, "bài không có ngôi thứ nhất - đọc như báo, không như blog cá nhân", (
            'kể lại như quá trình bạn tự đi qua: xưng "mình", gọi "bạn"'
        )


# --------------------------------------------------------------------------
# FORMAT
# --------------------------------------------------------------------------


@rule("FMT-F1", "error")
def frontmatter(doc: Doc, opt: Options):
    fm = doc.frontmatter
    if not fm:
        yield 0, "thiếu frontmatter", "thêm frontmatter với title + description"
        return
    for field_name in ("title", "description"):
        if not str(fm.get(field_name, "")).strip():
            yield 0, f"frontmatter thiếu '{field_name}'", f"thêm {field_name} vào frontmatter"
    desc = str(fm.get("description", ""))
    if len(desc) > 160:
        yield 0, f"description dài {len(desc)} ký tự (tối đa 160)", "cắt ngắn description"


_UNESCAPED_DOLLAR = re.compile(r"(?<!\\)\$\s?\d")


@rule("FMT-F2", "error")
def unescaped_dollar(doc: Doc, opt: Options):
    for m in _UNESCAPED_DOLLAR.finditer(doc.masked):
        yield m.start(), f'"{m.group(0)}" - KaTeX sẽ nuốt cặp $...$ thành công thức', (
            r"escape thành \$"
        )


def run(doc: Doc, opt: Options) -> list[Finding]:
    findings: list[Finding] = []
    ignored = doc.ignored_rules
    for rid, severity, fn in RULES:
        if rid in ignored:
            continue
        for idx, message, fix in fn(doc, opt):
            line, col = doc.line_col(idx)
            findings.append(Finding(rid, severity, line, col, message, fix))
    findings.sort(key=lambda f: (f.line, f.col, f.rule))
    return findings
