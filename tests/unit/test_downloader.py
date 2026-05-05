import pytest
from unittest.mock import patch, MagicMock
from agent.services.downloader import download_video

@pytest.mark.asyncio
async def test_download_video_success():
    mock_url = "https://www.youtube.com/shorts/q2m7M0cM0Ew"

    with patch('agent.services.downloader.yt_dlp.YoutubeDL') as mock_ydl:
        # Configure the mock
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance

        # Mock extract_info return value
        mock_instance.extract_info.return_value = {
            "title": "Test Video",
            "description": "Test Description",
            "tags": ["test"],
            "uploader": "Test Uploader",
            "duration": 15
        }

        # Call the function
        result = await download_video(mock_url, "test_task_123")

        # Assertions
        assert result["title"] == "Test Video"
        assert result["original_url"] == mock_url
        assert "test_task_123.mp4" in result["local_path"]
        assert result["duration"] == 15

        # Verify extract_info was called with download=True
        mock_instance.extract_info.assert_called_once_with(mock_url, download=True)

@pytest.mark.asyncio
async def test_download_video_failure():
    mock_url = "https://invalid.url"

    with patch('agent.services.downloader.yt_dlp.YoutubeDL') as mock_ydl:
        mock_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_instance

        # Make extract_info raise an exception
        mock_instance.extract_info.side_effect = Exception("Download failed")

        with pytest.raises(Exception) as exc_info:
            await download_video(mock_url, "test_task_fail")

        assert "Download failed" in str(exc_info.value)
