#!/usr/bin/env bash
# Boot omelet-cli. Chạy lại nhiều lần không sao.
set -euo pipefail
cd "$(dirname "$0")"

pip install -q -e ".[dev]"
python -m pytest tests -q --no-header

echo
echo "omelet đã cài editable: code trên đĩa là code đang chạy."
echo "Repo blog (~/blog) phụ thuộc vào những lệnh này - đừng đổi tên chúng mà không"
echo "chạy 'python3 tools/check.py' bên đó."
omelet --help | sed -n '/Commands:/,$p'
