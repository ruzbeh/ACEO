"""Faceless content-channel tools (supplement / medical-discovery reels).

Separate from aeco/tools/video (the Headshot AI ad harness). Publishes organic
short-form content to YouTube (and later Instagram), rather than paid FB ads.
"""
from aeco.tools.content.youtube_publisher import (
    YouTubeError,
    refresh_access_token,
    upload_short,
)

__all__ = ["YouTubeError", "refresh_access_token", "upload_short"]
