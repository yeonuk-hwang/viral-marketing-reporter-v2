"""환경 정보 수집 및 로깅 유틸리티"""

import platform
from typing import Dict, Any


def get_environment_info() -> Dict[str, Any]:
    """현재 실행 환경의 상세 정보를 수집합니다.

    Returns:
        환경 정보를 담은 딕셔너리
    """
    env_info = {}

    # OS 정보
    env_info["os"] = {
        "system": platform.system(),  # Darwin, Windows, Linux
        "release": platform.release(),  # 24.6.0
        "version": platform.version(),  # Darwin Kernel Version...
        "machine": platform.machine(),  # arm64, x86_64
        "processor": platform.processor(),  # arm, i386
    }

    # 화면 정보 (Qt 사용 가능할 때만)
    try:
        from PySide6.QtWidgets import QApplication

        if QApplication.instance():
            app = QApplication.instance()

            # 모든 스크린 정보 수집
            screens_info = []
            for idx, screen in enumerate(app.screens()):
                geometry = screen.geometry()
                is_primary = screen == app.primaryScreen()
                screen_data = {
                    "index": idx,
                    "is_primary": is_primary,
                    "width": geometry.width(),
                    "height": geometry.height(),
                    "dpi": screen.logicalDotsPerInch(),
                    "device_pixel_ratio": screen.devicePixelRatio(),
                    "name": screen.name(),
                }
                screens_info.append(screen_data)

            env_info["screens"] = screens_info
    except Exception:
        # Qt가 초기화되지 않았거나 화면 정보를 가져올 수 없음
        pass

    return env_info


def format_environment_info(env_info: Dict[str, Any]) -> str:
    """환경 정보를 사람이 읽기 쉬운 형식으로 포맷합니다.

    Args:
        env_info: get_environment_info()로부터 얻은 환경 정보

    Returns:
        포맷된 문자열
    """
    lines = ["=" * 60, "Environment Information", "=" * 60]

    # OS 정보
    lines.append("\n[Operating System]")
    os_info = env_info.get("os", {})
    lines.append(f"  System: {os_info.get('system', 'Unknown')}")
    lines.append(f"  Release: {os_info.get('release', 'Unknown')}")
    lines.append(f"  Version: {os_info.get('version', 'Unknown')}")
    lines.append(f"  Machine: {os_info.get('machine', 'Unknown')}")
    lines.append(f"  Processor: {os_info.get('processor', 'Unknown')}")

    # 화면 정보 (모든 모니터)
    screens = env_info.get("screens", [])
    if screens:
        lines.append(f"\n[Screens] (Total: {len(screens)})")
        for screen in screens:
            primary_marker = " [PRIMARY]" if screen.get("is_primary") else ""
            lines.append(f"\n  Screen {screen.get('index', '?')}{primary_marker}:")
            lines.append(f"    Name: {screen.get('name', 'Unknown')}")
            lines.append(
                f"    Resolution: {screen.get('width', '?')}x{screen.get('height', '?')}"
            )
            lines.append(f"    DPI: {screen.get('dpi', '?')}")
            lines.append(
                f"    Device Pixel Ratio: {screen.get('device_pixel_ratio', '?')}"
            )

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
