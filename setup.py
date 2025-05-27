"""
Setup configuration for Omelet package
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")

# Read version from package
version = "0.1.0"
init_path = Path(__file__).parent / "omelet" / "__init__.py"
if init_path.exists():
    with open(init_path, "r") as f:
        for line in f:
            if line.startswith("__version__"):
                version = line.split("=")[1].strip().strip('"').strip("'")
                break

setup(
    name="omelet",
    version=version,
    author="Nguyen Anh Binh",
    author_email="socrat.nguyeannhbinh@gmail.com",
    description="Automatically upload local images in Markdown files to a server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://omelet.tech",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0",
        "requests>=2.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.900",
        ],
    },
    entry_points={
        "console_scripts": [
            "omelet=omelet.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)