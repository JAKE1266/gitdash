import subprocess
import tempfile
import unittest
from pathlib import Path

from gitdash.core import GitError, collect_status


class RepositoryTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Gitdash Test")
        self.git("config", "user.email", "gitdash@example.invalid")
        self.tracked = self.repo / "tracked.txt"
        self.tracked.write_text("initial\n", encoding="utf-8")
        self.git("add", "tracked.txt")
        self.git("commit", "-m", "initial commit")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args, check=True):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=check,
        )

    def test_clean_repository(self):
        status = collect_status(str(self.repo))

        self.assertEqual(status.branch, "main")
        self.assertFalse(status.detached)
        self.assertIsNone(status.upstream)
        self.assertEqual((status.staged, status.modified, status.untracked, status.conflicted), (0, 0, 0, 0))
        self.assertFalse(status.dirty)
        self.assertEqual(len(status.commits), 1)
        self.assertEqual(status.commits[0].subject, "initial commit")
        self.assertEqual(status.to_dict()["commits"][0]["sha"], status.commits[0].sha)

    def test_counts_staged_modified_and_untracked_files(self):
        (self.repo / "staged.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "staged.txt")
        self.tracked.write_text("changed\n", encoding="utf-8")
        (self.repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")

        status = collect_status(str(self.repo))

        self.assertEqual(status.staged, 1)
        self.assertEqual(status.modified, 1)
        self.assertEqual(status.untracked, 1)
        self.assertEqual(status.conflicted, 0)
        self.assertTrue(status.dirty)

    def test_counts_staged_rename(self):
        self.git("mv", "tracked.txt", "renamed.txt")

        status = collect_status(str(self.repo))

        self.assertEqual(status.staged, 1)
        self.assertEqual(status.modified, 0)
        self.assertEqual(status.untracked, 0)

    def test_upstream_ahead_and_behind(self):
        self.git("remote", "add", "origin", str(self.repo))
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("branch", "--set-upstream-to=origin/main", "main")
        self.tracked.write_text("ahead\n", encoding="utf-8")
        self.git("commit", "-am", "ahead commit")

        status = collect_status(str(self.repo))
        self.assertEqual(status.upstream, "origin/main")
        self.assertEqual((status.ahead, status.behind), (1, 0))

        self.git("checkout", "-b", "remote-work")
        self.tracked.write_text("behind\n", encoding="utf-8")
        self.git("commit", "-am", "remote commit")
        remote_head = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "main")
        self.git("update-ref", "refs/remotes/origin/main", remote_head)

        status = collect_status(str(self.repo))
        self.assertEqual((status.ahead, status.behind), (0, 1))

    def test_counts_merge_conflicts(self):
        self.git("checkout", "-b", "feature")
        self.tracked.write_text("feature\n", encoding="utf-8")
        self.git("commit", "-am", "feature change")
        self.git("checkout", "main")
        self.tracked.write_text("main\n", encoding="utf-8")
        self.git("commit", "-am", "main change")
        self.git("merge", "feature", check=False)

        status = collect_status(str(self.repo))

        self.assertEqual(status.conflicted, 1)
        self.assertEqual(status.to_dict()["conflicted"], 1)

    def test_detached_head_and_stash(self):
        self.tracked.write_text("stashed\n", encoding="utf-8")
        self.git("stash", "push", "-m", "test stash")
        self.git("checkout", "--detach", "HEAD")

        status = collect_status(str(self.repo))

        self.assertTrue(status.detached)
        self.assertIsNone(status.branch)
        self.assertEqual(status.stashes, 1)

    def test_unborn_branch_has_no_commits(self):
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(empty)], check=True, capture_output=True)

        status = collect_status(str(empty))

        self.assertEqual(status.branch, "main")
        self.assertEqual(status.commits, [])

    def test_subdirectory_resolves_repository_root(self):
        nested = self.repo / "src" / "nested"
        nested.mkdir(parents=True)

        status = collect_status(str(nested))

        self.assertEqual(Path(status.root), self.repo.resolve())
        self.assertEqual(Path(status.path), nested.resolve())

    def test_rejects_missing_path_and_non_repository(self):
        with self.assertRaisesRegex(GitError, "path does not exist"):
            collect_status(str(self.repo / "missing"))

        other = Path(self.temp.name) / "other"
        other.mkdir()
        with self.assertRaises(GitError):
            collect_status(str(other))

    def test_rejects_bare_repository(self):
        bare = Path(self.temp.name) / "bare.git"
        subprocess.run(
            ["git", "clone", "--bare", str(self.repo), str(bare)],
            check=True,
            capture_output=True,
        )

        with self.assertRaisesRegex(GitError, "bare repositories"):
            collect_status(str(bare))

    def test_limit_is_validated(self):
        with self.assertRaises(ValueError):
            collect_status(str(self.repo), limit=0)


if __name__ == "__main__":
    unittest.main()
