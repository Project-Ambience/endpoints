import pytest
from unittest.mock import patch
from download_model import install_model_and_notify


@patch("download_model.snapshot_download")
@patch("download_model.requests.post")
def test_install_model_success(mock_post, mock_snapshot):
    install_model_and_notify("bert-base-uncased", "http://fake-callback.com", "id-123")
    
    mock_snapshot.assert_called_once()
    mock_post.assert_called_once_with("http://fake-callback.com", json={"id": "id-123", "status": "success"})


@patch("download_model.snapshot_download", side_effect=Exception("Disk full"))
@patch("download_model.requests.post")
def test_install_model_failure(mock_post, mock_snapshot):
    install_model_and_notify("some-failing-model", "http://fake-callback.com", "id-999")
    
    mock_snapshot.assert_called_once()
    mock_post.assert_called_once_with("http://fake-callback.com", json={"id": "id-999", "status": "fail"})

