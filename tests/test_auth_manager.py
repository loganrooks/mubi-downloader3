import pytest
from unittest.mock import Mock, patch
from mubi_downloader import AuthManager

@pytest.fixture
def auth_manager():
    with patch('browser_cookie3.chrome'), \
         patch('browser_cookie3.firefox'), \
         patch('browser_cookie3.edge'):
        return AuthManager('chrome')

def test_auth_manager_init(auth_manager):
    """Test AuthManager initialization"""
    assert auth_manager.browser_name == 'chrome'
    assert auth_manager.logger is not None

@pytest.mark.parametrize('browser_name', ['chrome', 'firefox', 'edge'])
def test_supported_browsers(browser_name):
    """Test that supported browsers are handled correctly"""
    with patch('browser_cookie3.chrome'), \
         patch('browser_cookie3.firefox'), \
         patch('browser_cookie3.edge'):
        auth = AuthManager(browser_name)
        assert auth.browser_name == browser_name

def test_invalid_browser():
    """Test that invalid browser names raise ValueError"""
    with patch('browser_cookie3.chrome'), \
         patch('browser_cookie3.firefox'), \
         patch('browser_cookie3.edge'):
        with pytest.raises(ValueError, match="Unsupported browser"):
            AuthManager('unsupported_browser').get_browser_cookies()

@patch('browser_cookie3.chrome')
def test_get_browser_cookies(mock_chrome):
    """Test cookie retrieval"""
    mock_cookies = Mock()
    mock_chrome.return_value = mock_cookies
    
    auth_manager = AuthManager()
    result = auth_manager.get_browser_cookies()
    assert result == mock_cookies
    mock_chrome.assert_called_once()

@patch('browser_cookie3.chrome')
def test_generate_headers_success(mock_chrome):
    """Test successful header generation"""
    # Create mock cookies with proper attributes
    mock_cookie1 = type('Cookie', (), {
        'name': 'authToken',
        'value': 'test_token',
        'domain': 'mubi.com'
    })()
    
    mock_cookie2 = type('Cookie', (), {
        'name': 'dtCustomData',
        'value': 'test_data',
        'domain': 'mubi.com'
    })()
    
    mock_chrome.return_value = [mock_cookie1, mock_cookie2]
    
    auth_manager = AuthManager()
    headers = auth_manager.generate_headers()
    assert headers["Authorization"] == "Bearer test_token"
    assert headers["dt-custom-data"] == "test_data"

@patch('browser_cookie3.chrome')
def test_generate_headers_missing_cookies(mock_chrome):
    """Test header generation with missing cookies"""
    mock_chrome.return_value = []
    
    auth_manager = AuthManager()
    with pytest.raises(Exception) as exc_info:
        auth_manager.generate_headers()
    assert "No cookies found" in str(exc_info.value)