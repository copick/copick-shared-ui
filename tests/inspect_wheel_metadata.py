"""Inspect built wheel metadata for the shared-UI alpha runtime contract."""

import argparse
import email
import zipfile
from pathlib import Path


def inspect_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = email.message_from_bytes(archive.read(metadata_name))

    requirements = metadata.get_all("Requires-Dist", [])
    assert metadata["Requires-Python"] == ">=3.11"
    assert any(requirement.startswith("copick<3,>=2.0.0a1") for requirement in requirements), requirements
    assert any(requirement.startswith("numpy>=2.0.2") for requirement in requirements), requirements
    assert any(requirement.startswith("zarr<4,>=3.1.6") for requirement in requirements), requirements
    assert all("copick[all]" not in requirement for requirement in requirements), requirements


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    arguments = parser.parse_args()
    inspect_wheel(arguments.wheel)


if __name__ == "__main__":
    main()
