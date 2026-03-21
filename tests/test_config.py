"""tests/test_config.py -- focused tests for render-speed config defaults."""

import importlib
import os
import sys


def _reload_config():
    sys.modules.pop("config", None)
    import config  # noqa: PLC0415

    return importlib.reload(config)


def test_fast_render_defaults_enable_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("VIDEO_FAST_RENDER", raising=False)
    monkeypatch.delenv("VIDEO_PRESET", raising=False)
    monkeypatch.delenv("VIDEO_BITRATE", raising=False)
    monkeypatch.delenv("AUDIO_BITRATE", raising=False)
    monkeypatch.delenv("VIDEO_COLOR_GRADE", raising=False)

    config = _reload_config()

    assert config.VIDEO_FAST_RENDER is True
    assert config.VIDEO_PRESET == "veryfast"
    assert config.VIDEO_BITRATE == "8000k"
    assert config.AUDIO_BITRATE == "192k"
    assert config.VIDEO_COLOR_GRADE is False
    assert config.VIDEO_CINEMATIC_LOOK is True


def test_fast_render_can_be_overridden(monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("VIDEO_FAST_RENDER", "false")
    monkeypatch.delenv("VIDEO_PRESET", raising=False)
    monkeypatch.delenv("VIDEO_BITRATE", raising=False)
    monkeypatch.delenv("AUDIO_BITRATE", raising=False)
    monkeypatch.delenv("VIDEO_COLOR_GRADE", raising=False)

    config = _reload_config()

    assert config.VIDEO_FAST_RENDER is False
    assert config.VIDEO_PRESET == "slow"
    assert config.VIDEO_BITRATE == "16000k"
    assert config.AUDIO_BITRATE == "320k"
    assert config.VIDEO_COLOR_GRADE is True
    assert config.VIDEO_CINEMATIC_LOOK is True
