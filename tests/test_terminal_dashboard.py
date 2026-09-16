"""Terminal behavior uses disposable boards; never regenerates this pack's board."""
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock


PACK = Path(__file__).resolve().parents[1]
SCRIPT = PACK / "scripts/render-ticket-dashboard.py"
spec = importlib.util.spec_from_file_location("terminal_dashboard", SCRIPT)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class TerminalDashboardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="shepherd-terminal-")
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "Example project"
        (self.project / ".tickets").mkdir(parents=True)
        self.queue = self.project / ".tickets/queue.md"
        self.queue.write_text("# Queue\n")

    def ticket(self, number, state="Ready", title="A useful task"):
        ticket_id = f"TASK-{number:03}"
        path = self.project / f".tickets/{ticket_id}.md"
        path.write_text(f"# {ticket_id}\n\n## ID\n`{ticket_id}`\n\n## Title\n{title}\n\n## State\n`{state}`\n")
        with self.queue.open("a") as stream:
            stream.write(f"\n## {state}\n- `{ticket_id}`\n")
        return path

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--project", str(self.project), *args],
                              text=True, capture_output=True)

    def assert_fits(self, output, columns, rows):
        self.assertLessEqual(len(output.splitlines()), max(1, rows - 1))
        for line in output.splitlines():
            # Independently count normal terminal cells (CJK is double width).
            cells = sum(0 if unicodedata.category(char).startswith("M") else
                        2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in line)
            self.assertLessEqual(cells, max(1, columns - 1), line)
        self.assertNotIn("\x1b", output)
        self.assertNotIn("<br>", output)
        self.assertNotIn("| ---", output)

    def test_compact_order_overflow_and_unicode_at_pane_sizes(self):
        self.ticket(1, "Done")
        self.ticket(2, "Blocked", "Fix control \x1b[31m danger \x07 and 漢字 👩‍💻 " * 8)
        for number in range(3, 20):
            self.ticket(number, "In Progress", "Long title " * 20)
        for width, height in [(40, 8), (80, 12), (120, 12)]:
            with self.subTest(width=width, height=height):
                result = self.run_cli("--terminal", "--width", str(width), "--height", str(height))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_fits(result.stdout, width, height)
                self.assertIn("Example project", result.stdout)
                self.assertIn("TASK-002", result.stdout)
                self.assertIn("Blocked", result.stdout)
                self.assertNotIn("TASK-001", result.stdout)
                self.assertIn("hidden", result.stdout)
                self.assertIn("~", result.stdout)
                self.assertNotIn("\x07", result.stdout)
                self.assertNotIn("\u200d", result.stdout)

    def test_terminal_is_plain_read_only_and_preserves_default_outputs(self):
        self.ticket(1)
        generated = self.run_cli()
        self.assertEqual(generated.returncode, 0, generated.stderr)
        before = {p.relative_to(self.project): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.project.rglob("*") if p.is_file()}
        result = self.run_cli("--terminal", "--output", "unused/new.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TASK-001", result.stdout)
        self.assertIn("Ready", result.stdout)
        self.assertIn("A useful task", result.stdout)
        self.assertNotIn("Wrote", result.stdout)
        self.assertNotIn("\x1b", result.stdout)
        after = {p.relative_to(self.project): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.project / "unused").exists())
        validation = self.run_cli("--validate")
        self.assertEqual(validation.returncode, 0, validation.stderr)

    def test_empty_and_malformed_boards(self):
        result = self.run_cli("--terminal", "--width", "80", "--height", "12")
        self.assertIn("No tickets.", result.stdout)
        self.assertIn("0 tickets", result.stdout)
        self.assertFalse((self.project / "docs").exists())
        self.ticket(1, "Unexpected\x1b[2J")
        self.queue.unlink()
        result = self.run_cli("--terminal", "--width", "80", "--height", "12")
        self.assertEqual(result.returncode, 0)
        self.assertIn("warning(s)", result.stdout)
        self.assertIn("Missing .tickets/queue.md", result.stdout)
        self.assertIn("1 active", result.stdout)
        self.assert_fits(result.stdout, 80, 12)
        self.assertEqual(self.run_cli("--validate").returncode, 1)

    def test_tiny_panes_report_incomplete_view(self):
        self.ticket(1)
        for width, height in [(40, 3), (20, 2), (1, 1)]:
            result = self.run_cli("--terminal", "--width", str(width), "--height", str(height))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_fits(result.stdout, width, height)
        self.assertIn("enlarge pane", self.run_cli("--terminal", "--width", "80", "--height", "3").stdout)

    def test_watch_rejects_pipe_and_bad_arguments(self):
        result = self.run_cli("--watch")
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires a TTY", result.stderr)
        self.assertNotIn("\x1b", result.stdout)
        for args in [("--terminal", "--validate"), ("--terminal", "--width", "0"),
                     ("--terminal", "--height", "-2"), ("--terminal", "--interval", "nan"),
                     ("--terminal", "--interval", "inf"), ("--terminal", "--interval", "0")]:
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args).returncode, 2)

    def test_watch_only_redraws_on_content_change_or_resize_and_stops_cleanly(self):
        path = self.ticket(1)
        output = io.StringIO()
        dimensions = [80, 12]
        polls = 0

        def tick(interval):
            nonlocal polls
            self.assertEqual(interval, 0.25)
            polls += 1
            if polls == 1:
                self.assertEqual(output.getvalue().count("\x1b[2J"), 1)
            elif polls == 2:
                self.assertEqual(output.getvalue().count("\x1b[2J"), 1)
                # A field absent from the compact display still counts as a change.
                path.write_text(path.read_text() + "\n## Notes\nChanged\n")
            elif polls == 3:
                self.assertEqual(output.getvalue().count("\x1b[2J"), 2)
                dimensions[:] = [40, 8]
            elif polls == 4:
                self.assertEqual(output.getvalue().count("\x1b[2J"), 3)
                self.queue.unlink()
            elif polls == 5:
                self.assertEqual(output.getvalue().count("\x1b[2J"), 4)
                self.assertIn("warning(s)", output.getvalue())
                raise KeyboardInterrupt

        with mock.patch.object(dashboard, "terminal_dimensions", side_effect=lambda *_: tuple(dimensions)), \
                mock.patch.object(dashboard.time, "sleep", side_effect=tick), \
                mock.patch.object(dashboard.sys, "stdout", output):
            self.assertEqual(dashboard.show_terminal(self.project, None, None, True, 0.25), 0)
        self.assertEqual(polls, 5)
        self.assertFalse((self.project / "docs").exists())

    def test_dimensions_detect_stdout_and_respect_explicit_overrides(self):
        with mock.patch.object(dashboard.os, "get_terminal_size", return_value=os.terminal_size((120, 12))):
            self.assertEqual(dashboard.terminal_dimensions(None, None), (120, 12))
            self.assertEqual(dashboard.terminal_dimensions(40, 8), (40, 8))


if __name__ == "__main__":
    unittest.main()
