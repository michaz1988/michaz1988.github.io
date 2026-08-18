#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Fehler: $SCRIPT_DIR ist kein Git-Repository." >&2
    exit 1
fi

if [ -z "$(git status --porcelain)" ]; then
    echo "Keine lokalen Änderungen vorhanden."
    exit 0
fi

if [ "$#" -gt 0 ]; then
    COMMIT_MESSAGE=$*
else
    COMMIT_MESSAGE="Add-ons aktualisiert $(date '+%Y-%m-%d %H:%M:%S')"
fi

BRANCH=$(git branch --show-current)
if [ -z "$BRANCH" ]; then
    echo "Fehler: Kein aktiver Git-Branch gefunden." >&2
    exit 1
fi

echo "Änderungen werden aufgenommen ..."
git add -A

if git diff --cached --quiet; then
    echo "Keine commitfähigen Änderungen vorhanden."
    exit 0
fi

echo "Commit wird erstellt: $COMMIT_MESSAGE"
git commit -m "$COMMIT_MESSAGE"

echo "Commit wird nach origin/$BRANCH gepusht ..."
git push origin "$BRANCH"

echo "Fertig. Die Änderungen wurden nach origin/$BRANCH gepusht."
