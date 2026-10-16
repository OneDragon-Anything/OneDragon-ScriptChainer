import ctypes
import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, call, patch


def _load_privacy_screen():
    path = (
        Path(__file__).resolve().parents[1]
        / "src/script_chainer/utils/privacy_screen.py"
    )
    spec = importlib.util.spec_from_file_location("privacy_screen_under_test", path)
    module = importlib.util.module_from_spec(spec)
    runner_logging = ModuleType("script_chainer.win_exe.runner_logging")
    runner_logging.log = Mock()
    # Load the real module without opening Win32 DLLs or importing runner dependencies.
    with (
        patch.dict(sys.modules, {runner_logging.__name__: runner_logging}),
        patch.object(
            ctypes, "WinDLL", side_effect=lambda *a, **kw: Mock(), create=True
        ),
        patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True),
    ):
        spec.loader.exec_module(module)
    return module


privacy_screen = _load_privacy_screen()


class PrivacyScreenTests(unittest.TestCase):
    def setUp(self):
        self.hwnd = 1234
        self.user32 = Mock()
        self.kernel32 = Mock()
        self.log = Mock()
        self.user32.GetSystemMetrics.side_effect = {
            privacy_screen.SM_XVIRTUALSCREEN: 0,
            privacy_screen.SM_YVIRTUALSCREEN: 0,
            privacy_screen.SM_CXVIRTUALSCREEN: 1920,
            privacy_screen.SM_CYVIRTUALSCREEN: 1080,
        }.__getitem__
        self.user32.CreateWindowExW.return_value = self.hwnd
        self.user32.SetWindowDisplayAffinity.return_value = 1
        self.user32.RegisterHotKey.return_value = 1
        self.user32.SetThreadDpiAwarenessContext.return_value = 1
        self.user32.GetMessageW.return_value = 0
        self.enterContext(
            patch.multiple(
                privacy_screen,
                _user32=self.user32,
                _kernel32=self.kernel32,
                _register_window_class=Mock(return_value=True),
                _enable_click_through=Mock(return_value=True),
                log=self.log,
            )
        )
        self.enterContext(patch.object(ctypes, "set_last_error", create=True))
        self.enterContext(
            patch.object(ctypes, "get_last_error", return_value=5, create=True)
        )

    def test_create_sets_affinity_before_showing_window(self):
        self.assertEqual(privacy_screen._create_privacy_window("f12"), self.hwnd)

        calls = self.user32.mock_calls
        affinity = calls.index(
            call.SetWindowDisplayAffinity(
                self.hwnd,
                privacy_screen.WDA_EXCLUDEFROMCAPTURE,
            )
        )
        show = calls.index(call.ShowWindow(self.hwnd, privacy_screen.SW_SHOWNOACTIVATE))
        update = calls.index(call.UpdateWindow(self.hwnd))
        self.assertLess(affinity, show)
        self.assertLess(show, update)
        self.user32.DestroyWindow.assert_not_called()
        style = self.user32.CreateWindowExW.call_args.args[3]
        self.assertFalse(style & privacy_screen.WS_VISIBLE)

    def test_create_destroys_window_without_showing_it_when_affinity_fails(self):
        self.user32.SetWindowDisplayAffinity.return_value = 0

        self.assertIsNone(privacy_screen._create_privacy_window("f12"))

        self.user32.DestroyWindow.assert_called_once_with(self.hwnd)
        self.user32.ShowWindow.assert_not_called()
        self.user32.UpdateWindow.assert_not_called()
        self.user32.RegisterHotKey.assert_not_called()
        self.user32.SetTimer.assert_not_called()
        self.log.error.assert_called_once()
        self.assertEqual(self.log.error.call_args.args[1], 5)

    def test_create_still_cleans_up_when_click_through_fails(self):
        privacy_screen._enable_click_through.return_value = False

        self.assertIsNone(privacy_screen._create_privacy_window("f12"))

        self.user32.DestroyWindow.assert_called_once_with(self.hwnd)
        self.user32.SetWindowDisplayAffinity.assert_not_called()
        self.user32.ShowWindow.assert_not_called()

    def test_reveal_sets_affinity_before_showing_window(self):
        self.assertTrue(privacy_screen._reveal_privacy_window(self.hwnd))

        self.assertEqual(
            self.user32.mock_calls,
            [
                call.SetWindowDisplayAffinity(
                    self.hwnd, privacy_screen.WDA_EXCLUDEFROMCAPTURE
                ),
                call.ShowWindow(self.hwnd, privacy_screen.SW_SHOWNOACTIVATE),
                call.SetWindowPos(
                    self.hwnd,
                    privacy_screen.HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    privacy_screen.SWP_NOMOVE
                    | privacy_screen.SWP_NOSIZE
                    | privacy_screen.SWP_NOACTIVATE
                    | privacy_screen.SWP_SHOWWINDOW,
                ),
            ],
        )

    def test_reveal_keeps_window_hidden_when_affinity_fails(self):
        self.user32.SetWindowDisplayAffinity.return_value = 0

        self.assertFalse(privacy_screen._reveal_privacy_window(self.hwnd))

        self.user32.ShowWindow.assert_not_called()
        self.user32.SetWindowPos.assert_not_called()
        self.user32.DestroyWindow.assert_not_called()
        self.log.error.assert_called_once()
        self.assertEqual(self.log.error.call_args.args[1], 5)
        self.log.info.assert_not_called()

    def test_show_message_reports_reveal_result(self):
        self.user32.IsWindowVisible.return_value = 0
        for success in (0, 1):
            with self.subTest(success=success):
                self.user32.SetWindowDisplayAffinity.return_value = success
                result = privacy_screen._window_proc(
                    self.hwnd,
                    privacy_screen.WM_PRIVACY_SHOW,
                    0,
                    0,
                )
                self.assertEqual(result, success)

    def test_show_message_reports_success_for_already_visible_window(self):
        self.user32.IsWindowVisible.return_value = 1

        result = privacy_screen._window_proc(
            self.hwnd,
            privacy_screen.WM_PRIVACY_SHOW,
            0,
            0,
        )

        self.assertEqual(result, 1)
        self.user32.SetWindowDisplayAffinity.assert_not_called()
        self.user32.ShowWindow.assert_not_called()

    def test_hotkey_does_not_show_window_when_affinity_fails(self):
        self.user32.IsWindowVisible.return_value = 0
        self.user32.SetWindowDisplayAffinity.return_value = 0

        privacy_screen._window_proc(
            self.hwnd,
            privacy_screen.WM_HOTKEY,
            privacy_screen.EMERGENCY_HOTKEY_ID,
            0,
        )

        self.user32.ShowWindow.assert_not_called()
        self.user32.SetWindowPos.assert_not_called()

    def test_start_reports_failure_when_initial_affinity_fails(self):
        self.user32.SetWindowDisplayAffinity.return_value = 0
        screen = privacy_screen.PrivacyScreen()

        self.assertFalse(screen.start())
        screen._thread.join(timeout=1)

        self.assertFalse(screen._thread.is_alive())
        self.assertIsNone(screen._hwnd)
        self.user32.DestroyWindow.assert_called_once_with(self.hwnd)
        self.user32.ShowWindow.assert_not_called()

    def test_start_reports_success_when_initial_affinity_succeeds(self):
        screen = privacy_screen.PrivacyScreen()

        self.assertTrue(screen.start())
        screen._thread.join(timeout=1)

        self.assertEqual(screen._hwnd, self.hwnd)
        self.user32.ShowWindow.assert_called_once_with(
            self.hwnd,
            privacy_screen.SW_SHOWNOACTIVATE,
        )

    def test_start_existing_window_reports_reveal_result(self):
        self.user32.IsWindowVisible.return_value = 0
        self.user32.SendMessageW.side_effect = privacy_screen._window_proc
        for success in (0, 1):
            with self.subTest(success=success):
                self.user32.SetWindowDisplayAffinity.return_value = success
                screen = privacy_screen.PrivacyScreen()
                screen._thread = Mock()
                screen._thread.is_alive.return_value = True
                screen._hwnd = self.hwnd

                self.assertEqual(screen.start(), bool(success))

    def test_start_does_not_report_success_without_a_window(self):
        screen = privacy_screen.PrivacyScreen()
        screen._thread = Mock()
        screen._thread.is_alive.return_value = True

        self.assertFalse(screen.start())

        self.user32.SendMessageW.assert_not_called()


if __name__ == "__main__":
    unittest.main()
