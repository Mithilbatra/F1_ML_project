#!/usr/bin/env bash
# One-command launch for Pit Wall. Works from a fresh clone:
#   ./run.sh            -> installs deps if needed, self-builds data, serves UI
#   ./run.sh test       -> run the test suite
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "This project uses uv (https://docs.astral.sh/uv). Install it with:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

case "${1:-serve}" in
  test)  exec uv run --extra vision python -m pytest -q ;;
  *)     exec uv run --extra vision f1ml serve "${@:2}" ;;
esac
