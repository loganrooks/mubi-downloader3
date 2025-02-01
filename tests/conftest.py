import pytest
import os
import logging

@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for tests"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

@pytest.fixture
def temp_download_dir(tmp_path):
    """Create a temporary download directory"""
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    return str(download_dir)

@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return str(output_dir)

@pytest.fixture
def mock_environ(monkeypatch):
    """Setup mock environment variables"""
    env_vars = {
        "BROWSER": "chrome",
        "DOWNLOAD_DIR": "/tmp/download",
        "OUTPUT_DIR": "/tmp/output"
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars