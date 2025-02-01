#!/usr/bin/env python3
import os
import logging
import browser_cookie3
from typing import List, Dict, Optional

class AuthManager:
    """
    Manages authentication and cookie extraction for the Mubi downloader.
    Supports multiple browsers and provides error handling for authentication failures.
    """
    
    def __init__(self, browser_name: str = 'chrome'):
        """
        Initialize the AuthManager.
        
        Args:
            browser_name (str): Name of the browser to use (chrome, firefox, edge)
        """
        self.browser_name = browser_name.lower()
        self.logger = logging.getLogger('AuthManager')
        
        # WSL2 paths
        self.wsl_paths = self._get_wsl_paths()
        
    def _get_wsl_paths(self) -> Dict[str, str]:
        """Get browser cookie paths for WSL2 environment"""
        paths = {}
        windows_home = None
        
        # Try to get Windows username from environment
        if 'USERPROFILE' in os.environ:
            windows_home = os.environ['USERPROFILE'].replace('\\', '/')
            if windows_home.startswith('C:'):
                windows_home = f"/mnt/c{windows_home[2:]}"
        
        # If not found, try to detect from /mnt/c/Users
        if not windows_home and os.path.exists('/mnt/c/Users'):
            try:
                users = os.listdir('/mnt/c/Users')
                # Filter out default Windows folders
                users = [u for u in users if u not in ['Public', 'Default', 'Default User', 'All Users']]
                if len(users) == 1:
                    windows_home = f'/mnt/c/Users/{users[0]}'
            except (FileNotFoundError, PermissionError):
                pass
        
        if windows_home:
            paths['chrome'] = f"{windows_home}/AppData/Local/Google/Chrome/User Data/Default/Cookies"
            paths['firefox'] = f"{windows_home}/AppData/Roaming/Mozilla/Firefox/Profiles"
            paths['edge'] = f"{windows_home}/AppData/Local/Microsoft/Edge/User Data/Default/Cookies"
        
        return paths

    def get_browser_cookies(self) -> List:
        """
        Get cookies from the selected browser.
        
        Returns:
            List: List of browser cookies
        
        Raises:
            ValueError: If browser is not supported
            Exception: If cookie extraction fails
        """
        try:
            browser_func = {
                'chrome': browser_cookie3.chrome,
                'firefox': browser_cookie3.firefox,
                'edge': browser_cookie3.edge
            }.get(self.browser_name)
            
            if not browser_func:
                raise ValueError(f"Unsupported browser: {self.browser_name}")
            
            # Check if we're in WSL2 and need to use Windows paths
            if self.wsl_paths and self.browser_name in self.wsl_paths:
                wsl_path = self.wsl_paths[self.browser_name]
                if os.path.exists(wsl_path):
                    self.logger.info(f"Using WSL2 cookie path: {wsl_path}")
                    return browser_func(cookie_file=wsl_path)
            
            # Try normal browser cookie extraction
            cookies = browser_func()
            if not cookies:
                raise Exception("No cookies found")
                
            return cookies
            
        except Exception as e:
            self.logger.error(f"Failed to load cookies from {self.browser_name}: {str(e)}")
            raise Exception(f"Cookie extraction failed: {str(e)}")

    def generate_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers from browser cookies.
        
        Returns:
            dict: Dictionary containing authentication headers

        Raises:
            Exception: If required cookies are not found
        """
        try:
            cookies = self.get_browser_cookies()
            auth_token = None
            dt_custom_data = None
            
            for cookie in cookies:
                if hasattr(cookie, 'domain') and cookie.domain == 'mubi.com':
                    if cookie.name == "authToken":
                        auth_token = cookie.value
                    elif cookie.name == "dtCustomData":
                        dt_custom_data = cookie.value
            
            if not auth_token or not dt_custom_data:
                raise Exception("Authentication cookies not found. Please log in to Mubi in your browser first.")
                
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'dt-custom-data': dt_custom_data
            }
            
            self.logger.info("Successfully generated authentication headers")
            return headers
            
        except Exception as e:
            self.logger.error(f"Header generation failed: {str(e)}")
            raise
