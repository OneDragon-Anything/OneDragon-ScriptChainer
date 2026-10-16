import ctypes
import importlib.util
import sys
import threading
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

    def test_start_timeout_destroys_late_window_without_stop(self):
        self._check_timed_out_window_is_destroyed(stop_before_creation=False)

    def test_stop_after_start_timeout_still_destroys_late_window(self):
        self._check_timed_out_window_is_destroyed(stop_before_creation=True)

    def _check_timed_out_window_is_destroyed(self, stop_before_creation):
        creating = threading.Event()
        release_creation = threading.Event()
        destroyed_by = []
        screen = privacy_screen.PrivacyScreen()
        self.user32.DestroyWindow.side_effect = (
            lambda hwnd: destroyed_by.append(threading.current_thread())
        )

        def create_window(close_key):
            creating.set()
            if not release_creation.wait(2):
                raise RuntimeError("Test did not release window creation")
            return self.hwnd

        self.enterContext(
            patch.object(privacy_screen, "_create_privacy_window", create_window)
        )
        self.enterContext(patch.object(privacy_screen, "START_TIMEOUT_SECONDS", 0))
        self.enterContext(patch.object(privacy_screen, "STOP_TIMEOUT_SECONDS", 0))
        worker = None
        try:
            self.assertFalse(screen.start())
            worker = screen._thread
            self.assertTrue(creating.wait(1))
            self.assertTrue(screen._stop_requested.is_set())
            if stop_before_creation:
                screen.stop()
            release_creation.set()
            worker.join(timeout=1)

            self.assertFalse(worker.is_alive())
            self.assertIsNone(screen._hwnd)
            self.user32.DestroyWindow.assert_called_once_with(self.hwnd)
            self.assertEqual(destroyed_by, [worker])
            self.user32.GetMessageW.assert_not_called()
        finally:
            release_creation.set()
            if worker is not None:
                worker.join(timeout=2)

    def test_start_timeout_closes_window_published_at_timeout_boundary(self):
        screen = privacy_screen.PrivacyScreen()
        ready = threading.Event()
        closed = threading.Event()
        wait_until_ready = ready.wait
        threading_proxy = Mock(wraps=threading)
        threading_proxy.Event.side_effect = [ready, threading.Event()]

        def timeout_after_publication(timeout):
            self.assertTrue(wait_until_ready(1))
            return False

        def get_message(*args):
            closed.wait(2)
            return 0

        self.user32.GetMessageW.side_effect = get_message
        self.user32.PostMessageW.side_effect = lambda *args: closed.set()
        with (
            patch.object(privacy_screen, "threading", threading_proxy),
            patch.object(ready, "wait", side_effect=timeout_after_publication),
        ):
            try:
                self.assertFalse(screen.start())
                screen._thread.join(timeout=1)

                self.assertFalse(screen._thread.is_alive())
                self.assertIsNone(screen._hwnd)
                self.assertTrue(screen._stop_requested.is_set())
                self.user32.PostMessageW.assert_called_once_with(
                    self.hwnd, privacy_screen.WM_CLOSE, 0, 0
                )
            finally:
                closed.set()
                screen._thread.join(timeout=2)

    def test_stop_during_creation_cancels_start_and_destroys_late_window(self):
        creating = threading.Event()
        release_creation = threading.Event()
        screen = privacy_screen.PrivacyScreen()
        results = []

        def create_window(close_key):
            creating.set()
            if not release_creation.wait(2):
                raise RuntimeError("Test did not release window creation")
            return self.hwnd

        self.enterContext(
            patch.object(privacy_screen, "_create_privacy_window", create_window)
        )
        self.enterContext(patch.object(privacy_screen, "STOP_TIMEOUT_SECONDS", 0))
        starter = threading.Thread(target=lambda: results.append(screen.start()))
        worker = None
        starter.start()
        try:
            self.assertTrue(creating.wait(1))
            worker = screen._thread
            screen.stop()
            starter.join(timeout=1)

            self.assertFalse(starter.is_alive())
            self.assertEqual(results, [False])
            self.assertTrue(worker.is_alive())
            self.assertIsNone(screen._thread)
            self.user32.PostMessageW.assert_not_called()

            release_creation.set()
            worker.join(timeout=1)
            screen.stop()

            self.assertFalse(worker.is_alive())
            self.assertIsNone(screen._hwnd)
            self.user32.DestroyWindow.assert_called_once_with(self.hwnd)
            self.user32.GetMessageW.assert_not_called()
        finally:
            release_creation.set()
            starter.join(timeout=2)
            if worker is not None:
                worker.join(timeout=2)

    def test_stop_posts_close_for_published_window(self):
        closed = threading.Event()
        screen = privacy_screen.PrivacyScreen()

        def get_message(*args):
            closed.wait(2)
            return 0

        self.user32.GetMessageW.side_effect = get_message
        self.user32.PostMessageW.side_effect = lambda *args: closed.set()
        try:
            self.assertTrue(screen.start())
            worker = screen._thread
            screen.stop()
            screen.stop()

            self.assertFalse(worker.is_alive())
            self.user32.PostMessageW.assert_called_once_with(
                self.hwnd, privacy_screen.WM_CLOSE, 0, 0
            )
            self.assertIsNone(screen._thread)
            self.assertIsNone(screen._hwnd)
        finally:
            closed.set()
            if screen._thread is not None:
                screen._thread.join(timeout=2)

    def test_old_creation_cannot_publish_handle_or_signal_restarted_screen(self):
        for old_hwnd in (self.hwnd, None):
            with self.subTest(old_hwnd=old_hwnd):
                self._check_restart_after_old_creation(old_hwnd)

    def _check_restart_after_old_creation(self, old_hwnd):
        self.user32.reset_mock()
        creating_old = threading.Event()
        creating_new = threading.Event()
        release_old = threading.Event()
        release_new = threading.Event()
        closed = threading.Event()
        screen = privacy_screen.PrivacyScreen()
        new_hwnd = 5678
        results = []

        def create_window(close_key):
            if not creating_old.is_set():
                creating_old.set()
                if not release_old.wait(2):
                    raise RuntimeError("Test did not release old creation")
                return old_hwnd
            creating_new.set()
            if not release_new.wait(2):
                raise RuntimeError("Test did not release new creation")
            return new_hwnd

        def get_message(*args):
            closed.wait(2)
            return 0

        self.user32.GetMessageW.side_effect = get_message
        self.user32.PostMessageW.side_effect = lambda *args: closed.set()
        with patch.object(
            privacy_screen, "_create_privacy_window", create_window
        ):
            with patch.object(privacy_screen, "START_TIMEOUT_SECONDS", 0):
                self.assertFalse(screen.start())
            old_worker = screen._thread
            old_ready = screen._ready
            old_stop = screen._stop_requested
            starter = threading.Thread(
                target=lambda: results.append(screen.start())
            )
            try:
                self.assertTrue(creating_old.wait(1))
                starter.start()
                self.assertTrue(creating_new.wait(1))
                new_worker = screen._thread
                self.assertIsNot(screen._ready, old_ready)
                self.assertIsNot(screen._stop_requested, old_stop)
                self.assertFalse(screen._stop_requested.is_set())

                release_old.set()
                old_worker.join(timeout=1)

                self.assertFalse(old_worker.is_alive())
                self.assertTrue(old_ready.is_set())
                self.assertFalse(screen._ready.is_set())
                self.assertIsNone(screen._hwnd)
                self.assertEqual(results, [])
                if old_hwnd is not None:
                    self.user32.DestroyWindow.assert_called_once_with(old_hwnd)
                else:
                    self.user32.DestroyWindow.assert_not_called()

                release_new.set()
                starter.join(timeout=1)

                self.assertFalse(starter.is_alive())
                self.assertEqual(results, [True])
                self.assertEqual(screen._hwnd, new_hwnd)
                self.assertIs(screen._thread, new_worker)
                screen.stop()

                self.assertFalse(new_worker.is_alive())
                self.user32.PostMessageW.assert_called_once_with(
                    new_hwnd, privacy_screen.WM_CLOSE, 0, 0
                )
            finally:
                release_old.set()
                release_new.set()
                closed.set()
                old_worker.join(timeout=2)
                if starter.ident is not None:
                    starter.join(timeout=2)
                if screen._thread is not None:
                    screen._thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
