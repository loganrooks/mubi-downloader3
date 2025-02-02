#!/usr/bin/env python3
import os
import logging
from typing import Optional, Dict, List

class EnvironmentDetector:
    """Detects and configures environment-specific settings"""
    
    def __init__(self, debug: bool = False):
        """
        Initialize environment detector.
        
        Args:
            debug (bool): Enable debug logging
        """
        self.logger = logging.getLogger('Environment')
        if debug:
            self.logger.setLevel(logging.DEBUG)
            
        self.is_wsl = False
        self.os_type = 'linux'
        self.gui_capable = True
        self._detect_environment()
        
    def _detect_environment(self):
        """Detect the current operating environment"""
        self.logger.debug("Detecting environment...")
        
        # Detect WSL
        if os.path.exists('/proc/version'):
            with open('/proc/version') as f:
                if 'microsoft' in f.read().lower():
                    self.is_wsl = True
                    self.os_type = 'wsl2'
                    self.logger.debug("Detected WSL2 environment")
                    self.logger.debug(f"WSL version: {open('/proc/version').read().strip()}")
                    
        # Detect native Windows
        elif os.name == 'nt':
            self.os_type = 'windows'
            self.logger.debug("Detected Windows environment")
            self.logger.debug(f"Windows version: {os.getenv('OS', 'Unknown')}")
        else:
            self.logger.debug("Detected Linux environment")
            try:
                with open('/etc/os-release') as f:
                    self.logger.debug(f"Linux distribution: {f.read()}")
            except:
                pass
            
        # Check GUI capability
        if 'DISPLAY' not in os.environ and not os.name == 'nt':
            self.gui_capable = False
            self.logger.debug("No GUI capability detected")
            
    def get_wsl_cookie_paths(self, browser: str) -> List[str]:
        """Get cookie paths for browsers in WSL2"""
        if not self.is_wsl:
            return []
            
        self.logger.debug("Getting WSL cookie paths...")
        windows_home = None
        
        # Try to get Windows username from environment
        if 'USERPROFILE' in os.environ:
            windows_home = os.environ['USERPROFILE'].replace('\\', '/')
            if windows_home.startswith('C:'):
                windows_home = f"/mnt/c{windows_home[2:]}"
                self.logger.debug(f"Found Windows home from USERPROFILE: {windows_home}")
        
        # If not found, try to detect from /mnt/c/Users
        if not windows_home and os.path.exists('/mnt/c/Users'):
            try:
                users = os.listdir('/mnt/c/Users')
                # Filter out default Windows folders
                users = [u for u in users if u not in ['Public', 'Default', 'Default User', 'All Users']]
                if len(users) == 1:
                    windows_home = f'/mnt/c/Users/{users[0]}'
                    self.logger.debug(f"Found Windows home from Users directory: {windows_home}")
                    self.logger.debug(f"Available users: {users}")
            except (FileNotFoundError, PermissionError) as e:
                self.logger.debug(f"Error detecting Windows home: {e}")
        
        if windows_home:
            paths = {
                'chrome': [
                    f"{windows_home}/AppData/Local/Google/Chrome/User Data/Default/Cookies",
                    f"{windows_home}/AppData/Local/Google/Chrome/User Data/Default/Network/Cookies",
                ],
                'firefox': [
                    f"{windows_home}/AppData/Roaming/Mozilla/Firefox/Profiles",
                ],
                'edge': [
                    f"{windows_home}/AppData/Local/Microsoft/Edge/User Data/Default/Cookies",
                    f"{windows_home}/AppData/Local/Microsoft/Edge/User Data/Default/Network/Cookies",
                ]
            }.get(browser, [])
            
            self.logger.debug(f"WSL cookie paths for {browser}: {paths}")
            return paths
        return []
    
    def get_browser_cookie_paths(self, browser: str) -> List[str]:
        """Get browser cookie paths for current environment"""
        self.logger.debug(f"Getting cookie paths for browser: {browser}")
        
        if self.is_wsl:
            paths = self.get_wsl_cookie_paths(browser)
            if paths:
                return paths
            
        if self.os_type == 'windows':
            base_paths = {
                'chrome': {
                    'base': '%LOCALAPPDATA%\\Google\\Chrome\\User Data',
                    'profiles': ['Default', 'Profile 1', 'Profile 2']
                },
                'firefox': {
                    'base': '%APPDATA%\\Mozilla\\Firefox\\Profiles',
                    'profiles': []  # Will scan directory
                },
                'edge': {
                    'base': '%LOCALAPPDATA%\\Microsoft\\Edge\\User Data',
                    'profiles': ['Default', 'Profile 1', 'Profile 2']
                }
            }
            
            paths = []
            browser_info = base_paths.get(browser)
            if browser_info:
                base = os.path.expandvars(browser_info['base'])
                if browser == 'firefox':
                    # Firefox uses random profile names, so we need to scan
                    if os.path.exists(base):
                        try:
                            profiles = [d for d in os.listdir(base) if d.endswith('.default') or '.default-release' in d]
                            paths.extend([os.path.join(base, p, 'cookies.sqlite') for p in profiles])
                        except Exception as e:
                            self.logger.debug(f"Error scanning Firefox profiles: {e}")
                else:
                    # Chrome/Edge use fixed profile names
                    for profile in browser_info['profiles']:
                        cookie_paths = [
                            os.path.join(base, profile, 'Cookies'),
                            os.path.join(base, profile, 'Network', 'Cookies')
                        ]
                        paths.extend(cookie_paths)
                        
        else:  # Linux
            paths = {
                'chrome': [
                    os.path.expanduser('~/.config/google-chrome/Default/Cookies'),
                    os.path.expanduser('~/.config/google-chrome/Default/Network/Cookies'),
                ],
                'firefox': [os.path.expanduser('~/.mozilla/firefox/')],
                'edge': [
                    os.path.expanduser('~/.config/microsoft-edge/Default/Cookies'),
                    os.path.expanduser('~/.config/microsoft-edge/Default/Network/Cookies'),
                ]
            }.get(browser, [])
            
        self.logger.debug(f"Found cookie paths: {paths}")
        # Log which paths actually exist
        for path in paths:
            self.logger.debug(f"Path exists '{path}': {os.path.exists(path)}")
        return paths
        
    def launch_browser(self, url: str) -> bool:
        """Launch browser with URL"""
        import webbrowser
        
        if not self.gui_capable:
            self.logger.debug("Cannot launch browser in non-GUI environment")
            return False
            
        try:
            self.logger.debug(f"Launching browser with URL: {url}")
            if webbrowser.open(url):
                self.logger.debug("Browser launch successful")
                return True
            self.logger.debug("Browser launch failed")
            return False
        except Exception as e:
            self.logger.error(f"Failed to launch browser: {e}")
            return False
            
    def normalize_path(self, path: str) -> str:
        """Normalize path for current environment"""
        self.logger.debug(f"Normalizing path: {path}")
        
        if self.os_type == 'windows':
            normalized = path.replace('/', '\\')
        else:
            normalized = path.replace('\\', '/')
            
        self.logger.debug(f"Normalized path: {normalized}")
        if os.path.exists(normalized):
            self.logger.debug(f"Normalized path exists")
        else:
            self.logger.debug(f"Normalized path does not exist")
        return normalized