"""FBKit — Video Downloader Service using yt-dlp."""
import asyncio
import logging
import os
import uuid
from typing import Dict, Any, Optional

import yt_dlp

from agent.config import MEDIA_DIR

logger = logging.getLogger(__name__)

# Ensure media directory exists
os.makedirs(MEDIA_DIR, exist_ok=True)

def _sync_download_video(url: str, output_path: str) -> Dict[str, Any]:
    """Synchronous function to download video using yt-dlp."""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        logger.info(f"Extracting info for {url}")
        info = ydl.extract_info(url, download=True)

        return {
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "tags": info.get("tags", []),
            "uploader": info.get("uploader", ""),
            "original_url": url,
            "local_path": output_path,
            "duration": info.get("duration", 0)
        }

async def download_video(url: str, task_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Asynchronously download a video from a URL.
    Returns a dictionary with metadata and local_path.
    """
    if not task_id:
        task_id = str(uuid.uuid4())

    filename = f"{task_id}.mp4"
    output_path = os.path.join(MEDIA_DIR, filename)
    output_path = os.path.abspath(output_path)

    logger.info(f"Starting download for {url} to {output_path}")

    try:
        metadata = await asyncio.to_thread(_sync_download_video, url, output_path)
        logger.info(f"Successfully downloaded {url} to {output_path}")
        return metadata
    except Exception as e:
        logger.error(f"Failed to download video from {url}: {str(e)}")
        raise
