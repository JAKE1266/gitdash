from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    date: str


@dataclass(frozen=True)
class RepositoryStatus:
    path: str
    root: str
    branch: Optional[str]
    detached: bool
    upstream: Optional[str]
    ahead: int
    behind: int
    staged: int
    modified: int
    untracked: int
    conflicted: int
    stashes: int
    commits: List[Commit]

    @property
    def dirty(self) -> bool:
        return bool(self.staged or self.modified or self.untracked or self.conflicted)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "root": self.root,
            "branch": self.branch,
            "detached": self.detached,
            "upstream": self.upstream,
            "ahead": self.ahead,
            "behind": self.behind,
            "staged": self.staged,
            "modified": self.modified,
            "untracked": self.untracked,
            "conflicted": self.conflicted,
            "stashes": self.stashes,
            "commits": [
                {
                    "sha": commit.sha,
                    "subject": commit.subject,
                    "date": commit.date,
                }
                for commit in self.commits
            ],
        }


def _git(repo: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable was not found on PATH") from exc

    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        if not message:
            message = "git {} exited with status {}".format(" ".join(args), result.returncode)
        raise GitError(message)
    return result


def _parse_branch(output: str) -> tuple:
    branch = None
    detached = False
    upstream = None
    ahead = 0
    behind = 0
    initial_oid = None

    for line in output.splitlines():
        if line.startswith("# branch.oid "):
            initial_oid = line.removeprefix("# branch.oid ")
        elif line.startswith("# branch.head "):
            head = line.removeprefix("# branch.head ")
            if head == "(detached)":
                detached = True
            else:
                branch = head
        elif line.startswith("# branch.upstream "):
            upstream = line.removeprefix("# branch.upstream ")
        elif line.startswith("# branch.ab "):
            for item in line.removeprefix("# branch.ab ").split():
                if item.startswith("+"):
                    ahead = int(item[1:])
                elif item.startswith("-"):
                    behind = int(item[1:])

    return branch, detached, upstream, ahead, behind, initial_oid


def _count_changes(output: str) -> tuple:
    staged = 0
    modified = 0
    untracked = 0
    conflicted = 0

    for line in output.splitlines():
        if line.startswith("u "):
            conflicted += 1
        elif line.startswith("? "):
            untracked += 1
        elif line.startswith(("1 ", "2 ")):
            x, y = line[2:4]
            if x not in " .":
                staged += 1
            if y not in " .":
                modified += 1

    return staged, modified, untracked, conflicted


def _read_commits(repo: Path, limit: int, initial_oid: Optional[str]) -> List[Commit]:
    if initial_oid == "(initial)":
        return []

    result = _git(
        repo,
        [
            "log",
            "-{}".format(limit),
            "--date=relative",
            "--format=%H%x1f%s%x1f%cd",
        ],
    )
    commits = []
    for line in result.stdout.splitlines():
        sha, subject, date = line.split("\x1f", 2)
        commits.append(Commit(sha=sha, subject=subject, date=date))
    return commits


def collect_status(path: str = ".", *, limit: int = 5) -> RepositoryStatus:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    repo = Path(path).expanduser()
    if not repo.exists():
        raise GitError("path does not exist: {}".format(repo))
    if not repo.is_dir():
        raise GitError("path is not a directory: {}".format(repo))
    repo = repo.resolve()

    if _git(repo, ["rev-parse", "--is-bare-repository"]).stdout.strip() == "true":
        raise GitError("bare repositories do not have a worktree to inspect")

    root = Path(_git(repo, ["rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    status_output = _git(
        root,
        ["status", "--porcelain=v2", "--branch", "--untracked-files=all"],
    ).stdout
    branch, detached, upstream, ahead, behind, initial_oid = _parse_branch(status_output)
    staged, modified, untracked, conflicted = _count_changes(status_output)
    stash_output = _git(root, ["stash", "list", "--format=%gd"]).stdout

    return RepositoryStatus(
        path=str(repo),
        root=str(root),
        branch=branch,
        detached=detached,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        staged=staged,
        modified=modified,
        untracked=untracked,
        conflicted=conflicted,
        stashes=len(stash_output.splitlines()),
        commits=_read_commits(root, limit, initial_oid),
    )
