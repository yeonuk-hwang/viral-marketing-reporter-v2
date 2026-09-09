from pathlib import Path
from zipfile import ZipFile

import pytest

from viral_marketing_reporter.infrastructure.support_bundle import (
    create_instagram_support_bundle,
)


def test_create_instagram_support_bundle_uses_latest_job_and_excludes_session(
    tmp_path: Path,
) -> None:
    instagram_root = tmp_path / "instagram"
    old_job = instagram_root / "old-job"
    latest_job = instagram_root / "latest-job"
    old_job.mkdir(parents=True)
    latest_job.mkdir()
    (old_job / "old.png").write_bytes(b"old")
    (latest_job / "result.png").write_bytes(b"png")
    (latest_job / "result_instagram_diagnostic.json").write_text("{}")
    (latest_job / "instagram_session.json").write_text("secret")
    (tmp_path / "debug.log").write_text("log")
    old_job.touch()
    latest_job.touch()

    bundle_path = create_instagram_support_bundle(tmp_path)

    with ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        assert "debug.log" in names
        assert "instagram/latest-job/result.png" in names
        assert "instagram/latest-job/result_instagram_diagnostic.json" in names
        assert "README.txt" in names
        assert all("old.png" not in name for name in names)
        assert all("instagram_session.json" not in name for name in names)


def test_create_instagram_support_bundle_requires_search_result(
    tmp_path: Path,
) -> None:
    (tmp_path / "instagram").mkdir()

    with pytest.raises(FileNotFoundError, match="검색 결과"):
        create_instagram_support_bundle(tmp_path)
