from __future__ import annotations

import textwrap

import pytest

from omelet.lint import Options, lint_path

OPT = Options()


def write_post(tmp_path, body: str, frontmatter: str = None, citations: str = None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    fm = frontmatter if frontmatter is not None else (
        'title: "Bài viết thử"\ndescription: "Một mô tả ngắn gọn"\n'
    )
    post = tmp_path / "main.mdx"
    post.write_text(f"---\n{fm}---\n\n{textwrap.dedent(body)}", encoding="utf-8")
    if citations is not None:
        (tmp_path / "citations.yaml").write_text(citations, encoding="utf-8")
    return post


def rules_fired(path, opt=OPT) -> set[str]:
    _, findings = lint_path(path, opt)
    return {f.rule for f in findings}


def test_ascii_dash_passes_em_dash_fails(tmp_path):
    ok = write_post(tmp_path / "ok", "Cái khó nhất không phải viết code đúng - đó là phần dễ.\n")
    assert "SLOP-P1" not in rules_fired(ok)

    bad = write_post(tmp_path / "bad", "Cái khó nhất — đó là phần dễ.\n")
    assert "SLOP-P1" in rules_fired(bad)


def test_code_fence_is_masked(tmp_path):
    """Em-dash trong code sample là code, không phải văn. Linter không được thấy nó."""
    post = write_post(
        tmp_path,
        """
        Đoạn code dưới đây minh hoạ cách parser xử lý dấu câu trong chuỗi đầu vào.

        ```python
        DASH = "—"  # em-dash
        print("Hy vọng bài viết hữu ích")
        ```
        """,
    )
    fired = rules_fired(post)
    assert "SLOP-P1" not in fired
    assert "SLOP-P3" not in fired


def test_ai_closing_in_tail(tmp_path):
    body = "Mở đầu bài viết.\n\n" + ("Một đoạn thân bài bình thường. " * 40) + \
        "\n\nTóm lại, đây là những gì mình đã học được.\n"
    post = write_post(tmp_path, body)
    assert "SLOP-P3" in rules_fired(post)


def test_number_without_source_fires_and_citation_silences_it(tmp_path):
    bad = write_post(tmp_path / "bad", "Burn rate của họ là 8,5 tỷ USD một năm, và đó là vấn đề.\n")
    assert "DEPTH-D1" in rules_fired(bad)

    ok = write_post(
        tmp_path / "ok",
        "Burn rate của họ là 8,5 tỷ USD một năm [@sec-filing], và đó là vấn đề.\n",
        citations='sec-filing:\n  title: "10-Q"\n  url: "https://www.sec.gov/x"\n  type: filing\n',
    )
    assert "DEPTH-D1" not in rules_fired(ok)


def test_dead_citation_key_suggests_the_near_miss(tmp_path):
    post = write_post(
        tmp_path,
        "Theo filing quý 3 [@sec-filng], con số này không khớp.\n",
        citations='sec-filing:\n  title: "10-Q"\n  url: "https://www.sec.gov/x"\n',
    )
    _, findings = lint_path(post)
    dead = [f for f in findings if f.rule == "DEPTH-D3"]
    assert dead and "sec-filing" in dead[0].message


def test_primary_source_ratio(tmp_path):
    cites = "".join(
        f'blog{i}:\n  title: "t"\n  url: "https://medium.com/{i}"\n  type: news\n'
        for i in range(5)
    )
    body = " ".join(f"Câu văn thứ {i} [@blog{i}]." for i in range(5))
    post = write_post(tmp_path, body + "\n", citations=cites)
    assert "DEPTH-D4" in rules_fired(post)


def test_primary_sources_pass(tmp_path):
    cites = "".join(
        f'paper{i}:\n  title: "t"\n  url: "https://arxiv.org/abs/{i}"\n  type: paper\n'
        for i in range(5)
    )
    body = " ".join(f"Câu văn thứ {i} [@paper{i}]." for i in range(5))
    post = write_post(tmp_path, body + "\n", citations=cites)
    assert "DEPTH-D4" not in rules_fired(post)


def test_choppy_rhythm(tmp_path):
    post = write_post(
        tmp_path,
        "Một header được trust. Một buffer được allocate. Heap chứa passwords. "
        "Bị leak như mở vòi nước. Và đó là vấn đề.\n",
    )
    assert "SLOP-P6" in rules_fired(post)


def test_clean_post_is_quiet(tmp_path):
    """Bài test quyết định linter có được giữ lại hay không: văn tử tế thì không kêu."""
    body = (
        "Hôm thứ ba tuần trước mình ngồi debug một đoạn code Rust đến 11 giờ đêm, "
        "và cho đến lúc đó mình vẫn tin rằng vấn đề nằm ở chỗ khác hoàn toàn.\n\n"
        "Cái mình nhận ra sau ba tiếng đọc lại stack trace là một thứ đơn giản đến "
        "mức khó chịu, và nó khiến mình phải viết lại gần như toàn bộ module.\n\n"
        "Bình\n"
    )
    post = write_post(tmp_path, body)
    assert rules_fired(post) == set()


@pytest.mark.parametrize(
    "text,rule",
    [
        ("Trong thời đại AI, mọi thứ đều thay đổi rất nhanh chóng.", "SLOP-P4"),
        ("Sản phẩm này mang lại giá trị thật sự cho người dùng.", "SLOP-P2"),
        ("Chi phí chạy hệ thống là $100 một tháng cho toàn bộ cluster.", "FMT-F2"),
        ("Bài này nói về hành trình của mình với Rust.", "SLOP-P2S"),
    ],
)
def test_single_rule_examples(tmp_path, text, rule):
    assert rule in rules_fired(write_post(tmp_path / rule, text + "\n"))


def test_lint_ignore_in_frontmatter(tmp_path):
    post = write_post(
        tmp_path,
        "Trong thời đại AI, mọi thứ đều thay đổi.\n",
        frontmatter='title: "t"\ndescription: "d"\nlint_ignore:\n  - SLOP-P4\n',
    )
    assert "SLOP-P4" not in rules_fired(post)
