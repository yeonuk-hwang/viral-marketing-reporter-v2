class InfrastructureError(Exception):
    """인프라스트럭처 계층에서 발생하는 모든 예외의 기반 클래스입니다."""
    pass


class ScreenshotError(InfrastructureError):
    """스크린샷 생성과 관련된 모든 예외의 기반 클래스입니다."""
    pass


class ScreenshotTargetMissingError(ScreenshotError):
    """스크린샷을 찍을 대상을 찾을 수 없을 때 발생하는 예외입니다."""
    pass
