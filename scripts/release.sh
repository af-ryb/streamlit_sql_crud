#!/usr/bin/env bash
#
# Tag a release.
#
#   scripts/release.sh 0.6.0            # check everything, create the tag locally
#   scripts/release.sh 0.6.0 --push     # ... and push it to origin
#   scripts/release.sh 0.6.0 --dry-run  # run every gate, create no tag
#   scripts/release.sh 0.6.0 -m "..."   # custom annotation message
#
# Why this exists rather than a bare `git tag`:
#
#   * Consumers install this library straight from git and pin it by tag, so a
#     tag whose commit carries a different version in pyproject.toml is a pin
#     that lies. Nothing else in the repo checks tag-against-version.
#
#   * A published tag must never move: pip and uv cache by URL+ref, so a
#     force-moved tag hands different code to different machines with no
#     signal at all. Pushing is therefore opt-in, and re-tagging an existing
#     version is refused outright — ship the next patch instead.
#
#   * The tag freezes whatever the commit holds, so it runs the same gates as
#     CI (lint, format, typecheck, tests) locally before anything is published.

set -euo pipefail

readonly RELEASE_BRANCH="master"
readonly REPO_URL="https://github.com/af-ryb/streamlit_sql_crud"
readonly PKG_NAME="streamlit_pydantic_crud"

die() { printf '\n\033[31mrelease: %s\033[0m\n' "$*" >&2; exit 1; }
warn() { printf '    \033[33mwarn\033[0m %s\n' "$*"; }
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok() { printf '    \033[32mok\033[0m  %s\n' "$*"; }

# Under --dry-run the checks about *where you are* — the branch, its remote,
# whether the tag is taken — soften to warnings, so the gates can be exercised
# from a feature branch. The checks about *what you would ship* — the declared
# version, the lockfile, lint, types, tests — stay fatal.
PLACE_WARNED=0
place_gate() {
    if [ "$DRY_RUN" -eq 1 ]; then PLACE_WARNED=1; warn "$*"; else die "$*"; fi
}

# Only claim a step passed when nothing in it warned.
ok_unless_warned() { [ "$PLACE_WARNED" -eq 1 ] || ok "$*"; }

usage() {
    sed -n '3,8p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

VERSION=""
MESSAGE=""
PUSH=0
DRY_RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --push)    PUSH=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -m)        MESSAGE="${2:-}"; [ -n "$MESSAGE" ] || die "-m needs a message"; shift 2 ;;
        -h|--help) usage 0 ;;
        -*)        die "unknown flag: $1" ;;
        *)         [ -z "$VERSION" ] || die "give exactly one version"; VERSION="$1"; shift ;;
    esac
done

[ -n "$VERSION" ] || usage 1
if [ "$DRY_RUN" -eq 1 ] && [ "$PUSH" -eq 1 ]; then
    die "--dry-run and --push contradict each other"
fi

# Accept `0.6.0` or `v0.6.0`; the tag carries the `v`, pyproject.toml does not.
VERSION="${VERSION#v}"
readonly VERSION
readonly TAG="v${VERSION}"

case "$VERSION" in
    [0-9]*.[0-9]*.[0-9]*) ;;
    *) die "'$VERSION' does not look like a version (expected e.g. 0.6.0)" ;;
esac

cd "$(git rev-parse --show-toplevel)"

# ---------------------------------------------------------------------------
# 1. The tag must not already exist
# ---------------------------------------------------------------------------

step "Tag $TAG is unused"

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    place_gate "$TAG already exists locally. A published tag must never move — ship the next patch version instead."
fi
if git ls-remote --exit-code --tags origin "$TAG" >/dev/null 2>&1; then
    place_gate "$TAG already exists on origin. A published tag must never move — ship the next patch version instead."
fi
ok_unless_warned "$TAG is free"

# ---------------------------------------------------------------------------
# 2. We are on an up-to-date, clean release branch
# ---------------------------------------------------------------------------

PLACE_WARNED=0
step "Working tree is $RELEASE_BRANCH, clean and current"

branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "$RELEASE_BRANCH" ] || place_gate "on '$branch'; releases are tagged from '$RELEASE_BRANCH'"

[ -z "$(git status --porcelain --untracked-files=no)" ] || die "working tree is dirty; commit or stash first"

if git fetch --quiet origin "$RELEASE_BRANCH" 2>/dev/null; then
    local_head="$(git rev-parse HEAD)"
    remote_head="$(git rev-parse "origin/$RELEASE_BRANCH")"
    if [ "$local_head" != "$remote_head" ]; then
        place_gate "HEAD ($(git rev-parse --short HEAD)) differs from origin/$RELEASE_BRANCH ($(git rev-parse --short "origin/$RELEASE_BRANCH")); pull or push first"
    fi
else
    place_gate "could not fetch origin/$RELEASE_BRANCH"
fi
ok_unless_warned "$RELEASE_BRANCH at $(git rev-parse --short HEAD), in sync with origin"

# ---------------------------------------------------------------------------
# 3. pyproject.toml declares exactly the version being tagged
# ---------------------------------------------------------------------------

step "Declared version matches $TAG"

declared="$(grep -m1 '^version[[:space:]]*=' pyproject.toml | sed 's/.*=[[:space:]]*"\(.*\)".*/\1/')"
[ "$declared" = "$VERSION" ] \
    || die "pyproject.toml says '$declared', tag says '$VERSION'. Bump it, run 'uv lock', commit."
ok "pyproject.toml says $VERSION"

# uv.lock pins the project at its own version, so a bump that stops at
# pyproject.toml leaves a lockfile that disagrees and shows up as phantom churn.
uv lock --check >/dev/null 2>&1 \
    || die "uv.lock is out of date with pyproject.toml. Run 'uv lock' and commit the result."
ok "uv.lock agrees with pyproject.toml"

# ---------------------------------------------------------------------------
# 4. The same gates as CI
# ---------------------------------------------------------------------------

step "Lint and format"
uv run --locked -- ruff check >/dev/null || die "ruff check failed (run 'uv run -- ruff check')"
uv run --locked -- ruff format --check >/dev/null || die "ruff format would reformat files (run 'task fix')"
ok "ruff clean"

step "Typecheck"
uv run --locked -- ty check >/dev/null || die "ty check failed (run 'uv run -- ty check')"
ok "ty clean"

step "Tests"
uv run --locked -- pytest -q || die "tests failed"
ok "tests passed"

# Consumers install the tagged commit as a wheel, not the source tree, so a
# module left out of the packaging config only breaks on their machine. Build
# from a pristine export of HEAD and import every module from a fresh venv.
step "Wheel installs and imports"
wheel_tmp="$(mktemp -d)"
trap 'rm -rf "$wheel_tmp"' EXIT
mkdir "$wheel_tmp/src"
git archive HEAD | tar -x -C "$wheel_tmp/src"
uv build --quiet --wheel --out-dir "$wheel_tmp/dist" "$wheel_tmp/src" \
    || die "uv build --wheel failed"
uv venv --quiet "$wheel_tmp/venv" || die "could not create a scratch venv"
uv pip install --quiet --python "$wheel_tmp/venv/bin/python" "$wheel_tmp"/dist/*.whl \
    || die "the wheel does not install"
# Bare-mode Streamlit logs runtime warnings on import; show them only on failure.
(cd "$wheel_tmp" && "$wheel_tmp/venv/bin/python" -I - "$PKG_NAME" 2>"$wheel_tmp/import.log") <<'PY' \
    || { cat "$wheel_tmp/import.log" >&2; die "the installed wheel does not import (missing sub-package in pyproject.toml?)"; }
import importlib, pkgutil, sys
pkg = importlib.import_module(sys.argv[1])
from streamlit_pydantic_crud import PydanticCrudUi, PydanticUi, SqlUi  # noqa: F401
for mod in pkgutil.walk_packages(pkg.__path__, f"{pkg.__name__}."):
    importlib.import_module(mod.name)
PY
ok "wheel installs and every module imports"

# ---------------------------------------------------------------------------
# 5. Tag
# ---------------------------------------------------------------------------

if [ "$DRY_RUN" -eq 1 ]; then
    step "Dry run — no tag created"
    printf '\nEvery gate that judges what would ship has passed for %s.\n' "$VERSION"
    printf 'Re-run on %s without --dry-run to create the tag.\n\n' "$RELEASE_BRANCH"
    exit 0
fi

step "Creating annotated tag $TAG"

[ -n "$MESSAGE" ] || MESSAGE="$PKG_NAME $VERSION"
git tag -a "$TAG" -m "$MESSAGE"
ok "$TAG -> $(git rev-parse --short HEAD)"

pin="$PKG_NAME @ git+$REPO_URL@$TAG"
if [ "$PUSH" -eq 1 ]; then
    step "Pushing $TAG to origin"
    git push origin "$TAG"
    ok "pushed"
    printf '\nPin it with:\n  %s\n\n' "$pin"
else
    printf '\nTag created locally, not pushed. When you are ready:\n\n  git push origin %s\n\nPin it with:\n  %s\n\n' "$TAG" "$pin"
fi
