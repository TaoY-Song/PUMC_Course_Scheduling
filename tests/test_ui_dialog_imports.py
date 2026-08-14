"""P2: ui.dialogs must expose one canonical class per dialog.

``ui/dialogs.py`` and ``ui/dialogs/`` used to coexist. The package shadowed the
module, so ``ui/__init__.py`` fell into its ``except ImportError`` branch and the
package re-loaded ``dialogs.py`` under the fake module name ``ui_dialogs_module``
via importlib — producing two distinct classes for the same dialog.
"""

import pytest

pytest.importorskip("PyQt5.QtWidgets", reason="PyQt5 not available")

DIALOGS = [
    "TimeSlotDialog",
    "CategorySettingDialog",
    "CreditSettingsDialog",
    "SupplementResultDialog",
]


def test_ui_package_exports_every_dialog():
    """__all__ used to silently degrade to just MainWindow."""
    import ui

    assert "MainWindow" in ui.__all__
    for name in DIALOGS:
        assert name in ui.__all__, f"{name} missing from ui.__all__"
        assert hasattr(ui, name)


@pytest.mark.parametrize("name", DIALOGS)
def test_dialog_identity_is_consistent(name):
    """ui.X and ui.dialogs.X must be the same class object."""
    import ui
    import ui.dialogs

    assert getattr(ui, name) is getattr(ui.dialogs, name)


@pytest.mark.parametrize("name", DIALOGS)
def test_dialogs_are_not_none(name):
    """The old importlib fallback returned None when loading failed."""
    import ui.dialogs

    assert getattr(ui.dialogs, name) is not None


@pytest.mark.parametrize("name", DIALOGS)
def test_dialogs_come_from_real_modules(name):
    """No class should live in the synthetic 'ui_dialogs_module' namespace."""
    import ui.dialogs

    module = getattr(ui.dialogs, name).__module__
    assert module.startswith("ui.dialogs."), f"{name} loaded from {module}"


def test_dialogs_py_no_longer_shadows_the_package():
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    assert not (project_root / "ui" / "dialogs.py").exists()
    assert (project_root / "ui" / "dialogs" / "course_dialogs.py").is_file()


def test_main_window_resolves_dialogs_through_the_package():
    import ui.dialogs
    import ui.main_window as main_window

    assert main_window.ui_dialogs is ui.dialogs
    assert main_window.ui_dialogs.CreditSettingsDialog is ui.dialogs.CreditSettingsDialog


def test_qt_add_course_uses_catalog_time_slots(monkeypatch, make_course):
    """The desktop path must preserve the same imported calendar data as Web."""
    import ui.main_window as main_window

    source = make_course("QT-TIME").course
    source.time_slots = make_course("QT-TIME").time_slots

    class Combo:
        def currentData(self):
            return source

        def clear(self):
            pass

        def setEnabled(self, _enabled):
            pass

    class Widget:
        def clear(self):
            pass

        def setEnabled(self, _enabled):
            pass

        def setChecked(self, _checked):
            pass

        def isChecked(self):
            return False

    window = main_window.MainWindow.__new__(main_window.MainWindow)
    window.class_combo = Combo()
    window.selected_courses = []
    window.online_checkbox = Widget()
    window.course_code_input = Widget()
    window.course_info_text = Widget()
    window.add_course_button = Widget()
    window.update_selected_courses_table = lambda: None
    window.update_stats = lambda: None
    monkeypatch.setattr(main_window.QMessageBox, "information", lambda *args: None)

    window.add_course()

    assert len(window.selected_courses[0].time_slots) == 1


def test_scheduling_thread_uses_deep_snapshot(make_course):
    """Editing the UI list after start must not mutate the worker input."""
    import ui.main_window as main_window

    original = [make_course("SNAPSHOT")]
    worker = main_window.SchedulingThread(object(), original)
    original[0].time_slots.clear()
    original.clear()

    assert len(worker.selected_courses) == 1
    assert len(worker.selected_courses[0].time_slots) == 1


def test_scheduling_runs_off_the_ui_thread():
    """P1: scheduling used to run synchronously on the Qt main thread."""
    from PyQt5.QtCore import QThread

    import ui.main_window as main_window

    assert hasattr(main_window, "SchedulingThread")
    assert issubclass(main_window.SchedulingThread, QThread)
