"""uploader.py — YouTube credential validation and video upload helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config

_YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def _is_fatal_oauth_error(exc: Exception) -> bool:
    """Return True when *exc* indicates non-retriable OAuth credential issues."""
    msg = str(exc).lower()
    return any(marker in msg for marker in ("invalid_scope", "invalid_grant", "invalid_client"))


def _parse_json_env(var_name: str, raw: str | None) -> dict[str, Any]:
    """Parse JSON from environment-backed config values with actionable errors."""
    if not raw:
        raise RuntimeError(f"{var_name} is missing. Set {var_name} in environment/GitHub Secrets.")
    try:
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"{var_name} contains invalid JSON.") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{var_name} must be a JSON object.")
    return data


def _build_credentials() -> Any:
    """Build and refresh Google OAuth2 credentials from configured JSON blobs."""
    client_secret_root = _parse_json_env("YOUTUBE_CLIENT_SECRET", config.YOUTUBE_CLIENT_SECRET_JSON)
    token_data = _parse_json_env("YOUTUBE_TOKEN", config.YOUTUBE_TOKEN_JSON)

    client_secret = (
        client_secret_root.get("installed")
        or client_secret_root.get("web")
        or client_secret_root
    )

    try:
        from google.auth.transport.requests import Request  # type: ignore[import]
        from google.oauth2.credentials import Credentials  # type: ignore[import]
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Google auth libraries are not installed.") from exc

    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri") or client_secret.get("token_uri"),
        client_id=client_secret.get("client_id"),
        client_secret=client_secret.get("client_secret"),
        scopes=_YOUTUBE_SCOPES,
    )

    if not getattr(creds, "refresh_token", None):
        raise RuntimeError("YOUTUBE_TOKEN is missing refresh_token. Re-authorize and update YOUTUBE_TOKEN.")

    try:
        creds.refresh(Request())
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "OAuth2 token refresh failed. Re-run auth flow and update YOUTUBE_TOKEN."
        ) from exc

    # Ensure downstream Google client does not fail on immutable scope objects.
    setattr(creds, "_scopes", None)
    setattr(creds, "_granted_scopes", None)
    return creds


def _build_youtube_service() -> Any:
    """Create an authenticated YouTube Data API service client."""
    try:
        from googleapiclient.discovery import build  # type: ignore[import]
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("google-api-python-client is not installed.") from exc
    return build("youtube", "v3", credentials=_build_credentials(), cache_discovery=False)


def validate_credentials() -> None:
    """Fail fast if YouTube credentials are invalid or channel access is missing."""
    try:
        youtube = _build_youtube_service()
        response = youtube.channels().list(part="id", mine=True).execute()
        if not response.get("items"):
            raise RuntimeError("No YouTube channel found for authenticated account.")
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"YouTube credential check failed: {exc}") from exc


def upload_video(video_path: Path | str, title: str, description: str, tags: list[str]) -> tuple[str, str]:
    """Upload a video file to YouTube and return ``(video_id, video_url)``."""
    path = Path(video_path)
    if not path.exists():
        raise RuntimeError(f"Video file not found: {path}")

    try:
        from googleapiclient.http import MediaFileUpload  # type: ignore[import]
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("google-api-python-client is not installed.") from exc

    youtube = _build_youtube_service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": str(config.YOUTUBE_CATEGORY_ID),
        },
        "status": {"privacyStatus": config.PRIVACY_STATUS},
    }

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(str(path), resumable=True, mimetype="video/mp4"),
        )
        response = request.execute()
        video_id = response.get("id")
        if not video_id:
            raise RuntimeError("YouTube API did not return a video id.")
        return video_id, f"https://www.youtube.com/watch?v={video_id}"
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"YouTube upload failed: {exc}") from exc
