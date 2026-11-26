import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gitdash.cli import main, render
from gitdash.core import collect_status


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.name", "Gitdash Test"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.email", "gitdash@example.invalid"],
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_json_output(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--json", str(self.repo)])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["branch"], "main")
        self.assertEqual(payload["commits"], [])

    def test_human_output_can_disable_color(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--no-color", str(self.repo)])

        self.assertEqual(code, 0)
        self.assertIn("State: CLEAN", stdout.getvalue())
        self.assertNotIn("\033[", stdout.getvalue())

    def test_render_color_is_explicit(self):
        status = collect_status(str(self.repo))
        output = render(status, color=True)

        self.assertIn("\033[", output)
        self.assertIn("no commits yet", output)

    def test_invalid_repository_returns_error_code(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as other:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main([other])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("gitdash:", stderr.getvalue())

    def test_watch_mode_returns_interrupted_code(self):
        stdout = io.StringIO()
        with patch("gitdash.cli.time.sleep", side_effect=KeyboardInterrupt), contextlib.redirect_stdout(stdout):
            code = main(["--watch", "0.5", str(self.repo)])

        self.assertEqual(code, 130)
        self.assertIn("State: CLEAN", stdout.getvalue())

    def test_invalid_watch_interval_is_rejected(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            main(["--watch", "0.1", str(self.repo)])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("at least 0.5 seconds", stderr.getvalue())

    def test_invalid_limit_is_rejected(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            main(["--limit", "21", str(self.repo)])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("between 1 and 20", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
