import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
    """모든 테스트에 일관된 뷰포트 크기를 적용하기 위한 Fixture."""
    return {  # pyright: ignore[reportUnknownVariableType]
        **browser_context_args,
        "viewport": {
            "width": 1920,
            "height": 1080,
        },
    }
