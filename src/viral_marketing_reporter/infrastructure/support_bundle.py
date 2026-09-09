from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from viral_marketing_reporter.infrastructure.paths import get_data_dir


def create_instagram_support_bundle(data_dir: Path | None = None) -> Path:
    """최근 Instagram 결과와 현재 로그를 고객 지원용 ZIP으로 묶습니다.

    인증 쿠키가 담긴 ``instagram_session.json``은 대상 경로 밖에 두며,
    명시적으로도 제외합니다.
    """
    root = data_dir or get_data_dir()
    instagram_root = root / "instagram"
    if not instagram_root.is_dir():
        raise FileNotFoundError("전달할 Instagram 검색 결과가 없습니다.")
    job_dirs = [path for path in instagram_root.iterdir() if path.is_dir()]
    if not job_dirs:
        raise FileNotFoundError("전달할 Instagram 검색 결과가 없습니다.")

    latest_job_dir = max(job_dirs, key=lambda path: path.stat().st_mtime)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle_path = root / f"instagram-support-{timestamp}.zip"

    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        log_path = root / "debug.log"
        if log_path.is_file():
            archive.write(log_path, "debug.log")

        for path in latest_job_dir.rglob("*"):
            if (
                not path.is_file()
                or path.is_symlink()
                or path.name == "instagram_session.json"
            ):
                continue
            archive.write(
                path,
                Path("instagram") / latest_job_dir.name / path.relative_to(latest_job_dir),
            )

        archive.writestr(
            "README.txt",
            "Instagram 문제 진단 자료입니다.\n"
            "로그인 세션과 쿠키는 포함하지 않습니다.\n"
            f"작업 ID: {latest_job_dir.name}\n",
        )

    return bundle_path
