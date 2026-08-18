"""Callback-shape tests for both supported thumbnail workers."""

import pytest

from copick_shared_ui.workers.chimerax import ChimeraXThumbnailWorker
from copick_shared_ui.workers.unified_workers import UnifiedThumbnailWorker, is_threading_available
from tests.helpers import DummyTomogram

pytestmark = pytest.mark.skipif(not is_threading_available(), reason="Qt threading is unavailable")


@pytest.mark.parametrize("worker_class", [UnifiedThumbnailWorker, ChimeraXThumbnailWorker])
def test_worker_callback_retains_thumbnail_id_and_precise_error(qtbot, worker_class, monkeypatch):
    callbacks = []
    worker = worker_class(DummyTomogram("unused"), "thumb-17", lambda *result: callbacks.append(result), True)
    worker._cache = None
    monkeypatch.setattr(worker, "generate_thumbnail_pixmap", lambda: (None, "storage unavailable"))

    worker.start()
    qtbot.waitUntil(lambda: bool(callbacks), timeout=5000)

    assert callbacks == [("thumb-17", None, "storage unavailable")]


@pytest.mark.parametrize("worker_class", [UnifiedThumbnailWorker, ChimeraXThumbnailWorker])
def test_cancelled_worker_does_not_emit_terminal_callback(worker_class):
    callbacks = []
    worker = worker_class(DummyTomogram("unused"), "thumb-17", lambda *result: callbacks.append(result), True)
    worker._cache = None
    worker._cancelled = True

    worker._on_worker_finished((None, "Cancelled"))

    assert callbacks == []
