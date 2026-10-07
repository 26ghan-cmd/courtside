#!/usr/bin/env bash
# One-time setup for Courtside. Run from the project folder:  bash setup.sh
set -euo pipefail
cd "$(dirname "$0")"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing $1. $2"; exit 1; }; }
need python3 "Install Python 3.11+ from https://www.python.org/downloads/"
need node    "Install Node 18+ from https://nodejs.org/"
need git     "Run: xcode-select --install"

echo "==> Backend: creating virtual environment and installing packages"
cd backend
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e ".[dev]"
echo "==> Backend: running tests"
.venv/bin/pytest -q
cd ..

echo "==> Extension: installing and building"
cd extension
npm install --silent
npm run build
cd ..

# The GitHub Actions file is shipped outside .github/ so it could be copied onto this Mac; move it into place.
if [ -f ci.yml ] && [ ! -f .github/workflows/ci.yml ]; then
  mkdir -p .github/workflows && mv ci.yml .github/workflows/ci.yml
fi

if [ ! -d .git ]; then
  echo "==> Git: creating repository"
  git init -q -b main
  git add -A
  git commit -q -m "Scaffold Courtside: FastAPI backend and Chrome MV3 extension"
fi

cat <<'EOF'

All set. Next:
  1. Start the backend:   cd backend && .venv/bin/uvicorn app.main:app --reload
  2. Load the extension:  chrome://extensions → Developer mode → Load unpacked → choose extension/dist
  3. Push to GitHub:      gh auth login   then   gh repo create courtside --private --source . --push
EOF
