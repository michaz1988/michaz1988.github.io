#!/usr/bin/env python3
"""Commit local add-on changes and push them to the publishing branch."""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parent
PUBLISH_BRANCH = "addons"


def git(*arguments, capture_output=False, check=True):
    """Run Git in this script's repository."""
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
    )


def git_output(*arguments):
    return git(*arguments, capture_output=True).stdout.strip()


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Lokale Add-on-Änderungen committen und nach origin/addons "
            "pushen. Der Push startet den GitHub-Workflow."
        )
    )
    parser.add_argument(
        "message",
        nargs="*",
        help="optionale Commit-Nachricht",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        if git_output("rev-parse", "--is-inside-work-tree") != "true":
            print("Fehler: Kein Git-Repository gefunden.", file=sys.stderr)
            return 1

        branch = git_output("branch", "--show-current")
        if not branch:
            print("Fehler: Kein aktiver Git-Branch gefunden.", file=sys.stderr)
            return 1
        if branch != PUBLISH_BRANCH:
            print(
                "Fehler: Aktiver Branch ist %r; erwartet wird %r."
                % (branch, PUBLISH_BRANCH),
                file=sys.stderr,
            )
            return 1

        if not git_output("status", "--porcelain"):
            print("Keine lokalen Änderungen vorhanden.")
            return 0

        message = " ".join(args.message).strip()
        if not message:
            message = "Add-ons aktualisiert %s" % datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        print("Änderungen werden aufgenommen ...", flush=True)
        git("add", "-A")

        staged = git("diff", "--cached", "--quiet", check=False)
        if staged.returncode == 0:
            print("Keine commitfähigen Änderungen vorhanden.")
            return 0
        if staged.returncode != 1:
            print("Fehler beim Prüfen der Änderungen.", file=sys.stderr)
            return staged.returncode

        print("Commit wird erstellt: %s" % message, flush=True)
        git("commit", "-m", message)

        print(
            "Commit wird nach origin/%s gepusht ..." % PUBLISH_BRANCH,
            flush=True,
        )
        git("push", "origin", PUBLISH_BRANCH)
        print("Fertig. Der GitHub-Workflow wurde durch den Push gestartet.")
        return 0
    except FileNotFoundError:
        print("Fehler: Git wurde nicht gefunden.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr.strip(), file=sys.stderr)
        print(
            "Fehler: Git-Befehl fehlgeschlagen (Exit-Code %d)."
            % error.returncode,
            file=sys.stderr,
        )
        return error.returncode


if __name__ == "__main__":
    sys.exit(main())
