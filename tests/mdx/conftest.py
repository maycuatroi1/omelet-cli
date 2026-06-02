from pathlib import Path

import pytest


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent / "golden"


@pytest.fixture
def citations_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "citations.yaml"
    p.write_text(
        "khosla2025:\n"
        "  type: news\n"
        "  title: Most AI Investments Will Lose Money\n"
        "  author: Vinod Khosla\n"
        "  publisher: The Information\n"
        "  date: 2025-02\n"
        "  url: https://theinformation.com/khosla\n"
        "amodei-2026:\n"
        "  type: podcast\n"
        "  title: We Are Near the End of the Exponential\n"
        "  author: Dario Amodei\n"
        "  date: 2026-02-13\n",
        encoding="utf-8",
    )
    return p
