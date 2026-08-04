from pathlib import Path


def get_data_dir() -> Path:
    """사용자가 결과와 진단 로그를 찾을 수 있는 공용 폴더입니다."""
    return Path.home() / "Downloads" / "viral-reporter"


def get_log_file_path() -> Path:
    return get_data_dir() / "debug.log"
