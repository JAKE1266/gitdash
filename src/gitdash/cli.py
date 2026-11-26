from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Optional, Sequence

from . import __version__
from .core import GitError, RepositoryStatus, collect_status


def _watch_interval(value: str) -> float:
    try:
        interval = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("watch interval must be a number") from exc
    if not math.isfinite(interval) or interval < 0.5:
        raise argparse.ArgumentTypeError("watch interval must be at least 0.5 seconds")
    return interval


def _commit_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("commit limit must be an integer") from exc
    if not 1 <= limit <= 20:
        raise argparse.ArgumentTypeError("commit limit must be between 1 and 20")
    return limit


def _configure_standard_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitdash",
        description="Show a concise dashboard for the Git repository at PATH.",
    )
    parser.add_argument("path", nargs="?", default=".", help="repository path (default: current directory)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--watch", type=_watch_interval, metavar="SECONDS", help="refresh the dashboard")
    parser.add_argument("--limit", type=_commit_limit, default=5, metavar="N", help="recent commits to show (1-20)")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    return parser


def render(status: RepositoryStatus, *, color: bool = False) -> str:
    branch = status.branch or "DETACHED"
    if status.upstream:
        tracking = " -> {} (ahead {}, behind {})".format(
            status.upstream,
            status.ahead,
            status.behind,
        )
    else:
        tracking = " (no upstream)"

    if status.conflicted:
        state = "CONFLICTS"
    elif status.dirty:
        state = "DIRTY"
    else:
        state = "CLEAN"

    lines = [
        "gitdash | {}".format(status.path),
        "Branch: {}{}".format(branch, tracking),
        "State: {} | {} staged, {} modified, {} untracked, {} conflicted".format(
            state,
            status.staged,
            status.modified,
            status.untracked,
            status.conflicted,
        ),
        "Stashes: {}".format(status.stashes),
        "Recent commits:",
    ]
    if status.commits:
        lines.extend(
            "  {}  {}  {}".format(commit.sha[:8], commit.date, commit.subject)
            for commit in status.commits
        )
    else:
        lines.append("  (no commits yet)")

    if not color:
        return "\n".join(lines)

    state_color = {"CLEAN": "32", "DIRTY": "33", "CONFLICTS": "31"}[state]
    lines[0] = "\033[1;36m{}\033[0m".format(lines[0])
    lines[2] = "\033[{}m{}\033[0m".format(state_color, lines[2])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_standard_streams()
    args = build_parser().parse_args(argv)
    use_color = (
        not args.no_color
        and not args.json
        and sys.stdout.isatty()
        and "NO_COLOR" not in os.environ
    )

    try:
        while True:
            status = collect_status(args.path, limit=args.limit)
            if args.json:
                print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))
            else:
                if args.watch and sys.stdout.isatty():
                    print("\033[2J\033[H", end="")
                print(render(status, color=use_color))

            if not args.watch:
                return 0
            time.sleep(args.watch)
    except GitError as exc:
        print("gitdash: {}".format(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
