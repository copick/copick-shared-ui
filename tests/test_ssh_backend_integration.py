"""Opt-in observable SSH reconnect validation using a mounted test service."""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from copick.impl.filesystem import CopickConfigFSSpec, CopickRootFSSpec

from copick_shared_ui.storage import open_coarsest_tomogram_array
from copick_shared_ui.workers.unified_workers import UnifiedThumbnailWorker
from tests.helpers import ArrayThumbnailWorker
from tests.test_core_entity_backends import _write_project

pytestmark = pytest.mark.integration


def _make_world_accessible(path: Path) -> None:
    for directory, _subdirectories, filenames in os.walk(path):
        os.chmod(directory, 0o777)
        for filename in filenames:
            os.chmod(Path(directory) / filename, 0o666)


def _thumbnail(root):
    worker = ArrayThumbnailWorker(root.get_run("run-1"))
    result, error = worker.generate_thumbnail_pixmap()
    assert error is None
    assert result is not None
    return result


def test_ssh_consecutive_and_post_drop_thumbnail_reads(qtbot):
    mount_root = os.environ.get("COPICK_SHARED_UI_SSH_MOUNT_ROOT")
    remote_root = os.environ.get("COPICK_SHARED_UI_SSH_REMOTE_ROOT")
    if mount_root is None or remote_root is None:
        pytest.skip("SSH mount and remote roots are not configured")

    options = json.loads(
        os.environ.get(
            "COPICK_SHARED_UI_SSH_FS_ARGS",
            '{"host":"127.0.0.1","port":2222,"username":"test.user","password":"password","known_hosts":null}',
        ),
    )
    with tempfile.TemporaryDirectory(prefix="shared-ui-", dir=mount_root) as temporary:
        local_project = Path(temporary) / "project"
        _write_project(f"local://{local_project}")
        _make_world_accessible(Path(temporary))
        remote_project = f"{remote_root.rstrip('/')}/{Path(temporary).name}/project"
        root = CopickRootFSSpec(
            CopickConfigFSSpec(
                name="shared-ui-ssh",
                description="Shared UI SSH fixture",
                version="1.0.0",
                pickable_objects=[],
                overlay_root=remote_project,
                overlay_fs_args=options,
            ),
        )

        first = _thumbnail(root)
        second = _thumbnail(root)
        np.testing.assert_array_equal(second, first)

        run = root.get_run("run-1")
        held_array = open_coarsest_tomogram_array(run.voxel_spacings[0].tomograms[0])

        # Force the real connection closed, then exercise public refresh/read behavior.
        root.fs_overlay._fs.client.abort()
        root.refresh()
        held_slice = np.asarray(held_array[held_array.shape[0] // 2, :, :])
        assert held_slice.size > 0
        recovered = _thumbnail(root)
        np.testing.assert_array_equal(recovered, first)

        callbacks = []
        workers = [
            UnifiedThumbnailWorker(
                root.get_run("run-1"),
                f"ssh-{index}",
                lambda *result: callbacks.append(result),
                True,
            )
            for index in range(4)
        ]
        for worker in workers:
            worker._cache = None
            worker.start()
        qtbot.waitUntil(lambda: len(callbacks) == len(workers), timeout=30000)

        assert {callback[0] for callback in callbacks} == {f"ssh-{index}" for index in range(4)}
        assert all(callback[1] is not None and callback[2] is None for callback in callbacks)
