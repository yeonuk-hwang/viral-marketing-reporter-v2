from pathlib import Path

import pytest

from viral_marketing_reporter.infrastructure import context


def test_find_google_chrome_prefers_configured_browser(monkeypatch, tmp_path: Path) -> None:
    browser = tmp_path / "chrome"
    browser.touch()
    monkeypatch.setenv("VIRAL_REPORTER_BROWSER_PATH", str(browser))

    assert context.find_google_chrome() == str(browser)


def test_find_google_chrome_falls_back_to_browser_on_path(monkeypatch) -> None:
    monkeypatch.delenv("VIRAL_REPORTER_BROWSER_PATH", raising=False)
    monkeypatch.setattr(
        context,
        "which",
        lambda executable: "/usr/bin/google-chrome" if executable == "google-chrome" else None,
    )

    assert context.find_google_chrome() == "/usr/bin/google-chrome"


def test_find_google_chrome_finds_default_windows_install(monkeypatch, tmp_path: Path) -> None:
    chrome = tmp_path / "Google/Chrome/Application/chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.touch()
    monkeypatch.delenv("VIRAL_REPORTER_BROWSER_PATH", raising=False)
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    monkeypatch.setattr(context, "which", lambda _executable: None)

    assert context.find_google_chrome() == str(chrome)


def test_find_google_chrome_ignores_bundled_playwright_chromium(monkeypatch) -> None:
    monkeypatch.delenv("VIRAL_REPORTER_BROWSER_PATH", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
    monkeypatch.setattr(
        context,
        "which",
        lambda executable: (
            r"C:\app\_internal\playwright\driver\package\.local-browsers\chromium-1187\chrome-win\chrome.exe"
            if executable == "chrome"
            else None
        ),
    )

    assert context.find_google_chrome() is None


def test_require_google_chrome_explains_how_to_install(monkeypatch) -> None:
    monkeypatch.setattr(context, "find_google_chrome", lambda: None)

    with pytest.raises(context.ChromeNotInstalledError, match="Chrome을 설치"):
        context.require_google_chrome()
