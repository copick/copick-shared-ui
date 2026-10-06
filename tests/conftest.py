import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def project(tmp_path):
    """A small filesystem copick project with a filament object."""
    import copick
    from copick.ops.open import new_config

    cfg = tmp_path / "config.json"
    new_config(str(cfg), str(tmp_path / "overlay"))
    root = copick.from_file(str(cfg))
    root.new_object(name="microtubule", is_particle=True, radius=120, filament={"polar": True})
    root.new_object(name="ribosome", is_particle=True, radius=150)
    root.new_object(name="membrane", is_particle=False)
    root.save_config(str(cfg))
    return copick.from_file(str(cfg)), cfg
