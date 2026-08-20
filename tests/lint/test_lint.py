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


def test_dead_citation_key_suggests_the_near_miss(tmp_path):
    post = write_post(
        tmp_path,
        "Theo filing quý 3 [@sec-filng], con số này không khớp.\n",
        citations='sec-filing:\n  title: "10-Q"\n  url: "https://www.sec.gov/x"\n',
    )
    _, findings = lint_path(post)
    dead = [f for f in findings if f.rule == "DEPTH-D3"]
    assert dead and "sec-filing" in dead[0].message


def test_clean_post_is_quiet(tmp_path):
    body = (
        "Ngày nay, hành trình này mang lại giá trị. Tóm lại, đây là lời kết. "
        "Ngắn. Dứt. Gọn. Lạnh.\n"
    )
    post = write_post(tmp_path, body)
    assert rules_fired(post) == set()


@pytest.mark.parametrize(
    "text,rule",
    [
        ("Chi phí chạy hệ thống là $100 một tháng cho toàn bộ cluster.", "FMT-F2"),
    ],
)
def test_single_rule_examples(tmp_path, text, rule):
    assert rule in rules_fired(write_post(tmp_path / rule, text + "\n"))


def test_lint_ignore_in_frontmatter(tmp_path):
    post = write_post(
        tmp_path,
        "Chi phí là $100.\n",
        frontmatter='title: "t"\ndescription: "d"\nlint_ignore:\n  - FMT-F2\n',
    )
    assert "FMT-F2" not in rules_fired(post)
