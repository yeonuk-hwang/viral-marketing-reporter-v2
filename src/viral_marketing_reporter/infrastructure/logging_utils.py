"""로깅 및 트레이싱 유틸리티"""

import functools
import time
from contextlib import contextmanager
from typing import Any, Callable

from loguru import logger


def log_function_call(func: Callable) -> Callable:
    """함수 호출을 자동으로 로깅하는 데코레이터

    함수의 시작, 종료, 실행 시간을 로깅합니다.
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        func_name = f"{func.__module__}.{func.__qualname__}"

        # 인자 로깅 (self 제외)
        args_repr = [repr(a) for a in args[1:]] if args and hasattr(args[0], '__class__') else [repr(a) for a in args]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)

        logger.debug(f"→ {func_name}({signature})")

        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            logger.debug(f"← {func_name} completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"✗ {func_name} failed after {elapsed:.3f}s: {e.__class__.__name__}: {e}"
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        func_name = f"{func.__module__}.{func.__qualname__}"

        args_repr = [repr(a) for a in args[1:]] if args and hasattr(args[0], '__class__') else [repr(a) for a in args]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)

        logger.debug(f"→ {func_name}({signature})")

        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            logger.debug(f"← {func_name} completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"✗ {func_name} failed after {elapsed:.3f}s: {e.__class__.__name__}: {e}"
            )
            raise

    # async 함수인지 sync 함수인지 확인
    import inspect
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


@contextmanager
def log_step(step_name: str, **extra_context):
    """단계별 작업을 로깅하는 컨텍스트 매니저

    Usage:
        with log_step("Searching Instagram", keyword="test"):
            # do work
            pass
    """
    logger.info(f"▶ {step_name}", **extra_context)
    start_time = time.perf_counter()

    try:
        yield
        elapsed = time.perf_counter() - start_time
        logger.info(f"✓ {step_name} completed in {elapsed:.3f}s", duration=elapsed, **extra_context)
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error(
            f"✗ {step_name} failed after {elapsed:.3f}s: {e.__class__.__name__}: {e}",
            duration=elapsed,
            error_type=e.__class__.__name__,
            **extra_context
        )
        raise


class PerformanceTracker:
    """성능 메트릭을 추적하는 클래스"""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.metrics = {}

    def start(self):
        """추적 시작"""
        self.start_time = time.perf_counter()
        logger.debug(f"Performance tracking started: {self.name}")

    def checkpoint(self, checkpoint_name: str):
        """중간 지점 기록"""
        if self.start_time is None:
            logger.warning(f"PerformanceTracker.start() not called for {self.name}")
            return

        elapsed = time.perf_counter() - self.start_time
        self.metrics[checkpoint_name] = elapsed
        logger.debug(
            f"Checkpoint '{checkpoint_name}' reached",
            tracker=self.name,
            elapsed=f"{elapsed:.3f}s"
        )

    def end(self) -> dict[str, float]:
        """추적 종료 및 메트릭 반환"""
        if self.start_time is None:
            logger.warning(f"PerformanceTracker.start() not called for {self.name}")
            return {}

        total_elapsed = time.perf_counter() - self.start_time
        self.metrics["total"] = total_elapsed

        logger.info(
            f"Performance metrics for {self.name}",
            **{k: f"{v:.3f}s" for k, v in self.metrics.items()}
        )

        return self.metrics


def log_with_context(**context_fields):
    """컨텍스트 정보를 추가하여 로깅하는 데코레이터

    Usage:
        @log_with_context(platform="instagram")
        async def search(...):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with logger.contextualize(**context_fields):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with logger.contextualize(**context_fields):
                return func(*args, **kwargs)

        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
