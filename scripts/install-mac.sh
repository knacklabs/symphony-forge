#!/bin/bash
set -euo pipefail

FORGE_VERSION=1.1.0

if [[ $# -gt 1 || ( $# -eq 1 && $1 != --check ) ]]; then
  echo 'Use: install-mac.sh [--check]' >&2
  exit 2
fi
check=${1:-}

has() { command -v "$1" >/dev/null 2>&1; }
missing() { echo "Missing: $1"; }
step() { echo "Installing $1..."; }
browsers_present() {
  local root="$HOME/Library/Caches/ms-playwright" kind path
  for kind in chromium firefox webkit; do
    local found=false
    for path in "$root/$kind"-*; do
      if [[ -d $path ]]; then found=true; break; fi
    done
    [[ $found == true ]] || return 1
  done
}
install_brew() {
  if has brew; then return; fi
  if [[ $check == --check ]]; then missing Homebrew; return; fi
  step Homebrew
  if ! has curl; then
    echo 'Curl is missing. Install curl, then run this script again.' >&2
    exit 1
  fi
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
}
brew_tool() {
  local label=$1 command=$2 package=$3
  if has "$command"; then
    if [[ $check != --check ]]; then echo "$label is ready."; fi
    return
  fi
  if [[ $check == --check ]]; then missing "$label"; return; fi
  step "$label"
  brew install "$package"
}

install_brew
brew_tool Git git git
brew_tool 'GitHub CLI' gh gh
brew_tool Node node node
if ! has docker; then
  if [[ $check == --check ]]; then missing Docker; else
    step Docker
    brew install --cask docker
  fi
elif [[ $check != --check ]]; then echo 'Docker is ready.'; fi
brew_tool uv uv uv

if ! has forge || [[ $(forge --version 2>/dev/null) != "forge v$FORGE_VERSION" ]]; then
  if [[ $check == --check ]]; then missing Forge; else
    step Forge
    uv tool install --force "symphony-forge==$FORGE_VERSION"
    export PATH="$HOME/.local/bin:$PATH"
  fi
elif [[ $check != --check ]]; then echo 'Forge is ready.'; fi

for tool in claude codex; do
  if has "$tool"; then
    if [[ $check != --check ]]; then echo "$tool is ready."; fi
    continue
  fi
  if [[ $tool == claude ]]; then label='Claude Code'; package='@anthropic-ai/claude-code'
  else label=Codex; package='@openai/codex'; fi
  if [[ $check == --check ]]; then missing "$label"; continue; fi
  step "$label"
  npm install -g "$package"
done

if browsers_present; then
  if [[ $check != --check ]]; then echo 'Playwright browsers are ready.'; fi
elif [[ $check == --check ]]; then missing 'Playwright browsers'
else
  step 'Playwright browsers'
  npx --yes playwright install chromium firefox webkit
fi

if [[ $check != --check ]]; then
  echo 'Setup finished. Forge version:'
  forge --version
  echo 'Next: sign in to Claude Code or Codex, then open your new repo.'
fi
