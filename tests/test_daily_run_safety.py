import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('daily_run_safety_under_test', ROOT / 'app/run.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class DailyRunSafetyTests(unittest.TestCase):
    def test_success_uses_app_working_directory(self):
        with patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as proc, patch('builtins.print'):
            self.assertEqual(runner.run(['python', 'example.py']), 0)
        proc.assert_called_once_with(['python', 'example.py'], cwd=runner._APP_DIR)

    def test_critical_failure_propagates_exit_code(self):
        with patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7)), patch('builtins.print'):
            with self.assertRaises(SystemExit) as caught:
                runner.run(['python', 'example.py'])
        self.assertEqual(caught.exception.code, 7)

    def test_explicit_warning_can_continue(self):
        with patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7)), patch('builtins.print'):
            self.assertEqual(runner.run(['python', 'example.py'], stop_on_error=False), 7)

    def check_gate(self, failing, files):
        executed = []
        def fake_process(cmd, **kwargs):
            executed.append(cmd[1])
            return subprocess.CompletedProcess(cmd, 9 if cmd[1] == failing else 0)
        with patch.object(runner, 'list_new_files', return_value=files), patch.object(runner.sys, 'argv', ['run.py', '--no-dashboard', '--no-effects']), patch.object(runner.subprocess, 'run', side_effect=fake_process), patch('builtins.print'):
            with self.assertRaises(SystemExit) as caught:
                runner.main()
        self.assertEqual(caught.exception.code, 9)
        self.assertEqual(executed[-1], failing)
        self.assertFalse(any('sync_pnl.py' in name or name == 'sheets_sync.py' for name in executed))
        return executed

    def test_finance_failure_blocks_publishers(self):
        self.assertEqual(self.check_gate('sync_finance.py', []), ['sync_monthly.py', 'sync_finance.py'])

    def test_monthly_failure_blocks_finance_and_publishers(self):
        self.assertEqual(self.check_gate('sync_monthly.py', []), ['sync_monthly.py'])

    def test_parser_failure_blocks_following_loaders_and_publishers(self):
        self.assertEqual(self.check_gate('parse_xlsx.py', ['example.xlsx']), ['parse_xlsx.py'])

    def test_database_path_is_app_absolute(self):
        self.assertEqual(Path(runner.DB_PATH), ROOT / 'app/ozon.db')
        self.assertTrue(Path(runner.DB_PATH).is_absolute())

    def test_batch_checks_error_before_opening_browser(self):
        batch = (ROOT / 'run.bat').read_text(encoding='utf-8-sig')
        command = batch.index('py run.py')
        gate = batch.index('if errorlevel 1 exit /b %errorlevel%', command)
        browser = batch.index('start ""')
        self.assertLess(command, gate)
        self.assertLess(gate, browser)
