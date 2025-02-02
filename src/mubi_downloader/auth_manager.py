#!/usr/bin/env python3
import os
import json
import base64
import logging
import webbrowser
import getpass
import sqlite3
import time
import tempfile
import shutil
import ctypes
from typing import List, Dict, Optional, Tuple
import browser_cookie3
from .environment import EnvironmentDetector

def is_admin() -> bool:
    """Check if running with admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

class AuthManager:
    """
    Manages authentication and cookie extraction for the Mubi downloader.
    Supports multiple browsers, platform-specific paths, and fallback authentication methods.
    """
    
    def __init__(self, browser_name: str = 'chrome', debug: bool = False):
        """
        Initialize the AuthManager.
        
        Args:
            browser_name (str): Name of the browser to use (chrome, firefox, edge)
            debug (bool): Enable debug logging
        """
        self.browser_name = browser_name.lower()
        self.logger = logging.getLogger('AuthManager')
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        self.env = EnvironmentDetector(debug=debug)
        self.auth_token = None
        self.dt_custom_data = None
        
        self.logger.debug(f"Initialized AuthManager for browser: {browser_name}")
        self.logger.debug(f"Running as admin: {is_admin()}")
        self.logger.debug(f"Environment type: {self.env.os_type}")

    def _read_locked_sqlite(self, db_path: str) -> List:
        """Read cookies from a potentially locked SQLite database"""
        self.logger.debug(f"Attempting to read SQLite database: {db_path}")
        
        if not os.path.exists(db_path):
            self.logger.debug(f"Database file does not exist: {db_path}")
            return []
            
        self.logger.debug(f"Database file size: {os.path.getsize(db_path)} bytes")
        self.logger.debug(f"Last modified: {os.path.getmtime(db_path)}")
        
        try:
            # Convert Windows path to URI format (handle backslashes and spaces)
            if os.name == 'nt':
                db_uri = db_path.replace('\\', '/').replace(' ', '%20')
            else:
                db_uri = db_path
                
            self.logger.debug(f"Converting path to URI format: {db_uri}")
            
            # Try to open the database in read-only mode with URI
            uri = f'file:{db_uri}?mode=ro&immutable=1'
            self.logger.debug(f"Opening database with URI: {uri}")
            
            # Increase timeout and add retry logic
            for attempt in range(3):
                try:
                    conn = sqlite3.connect(uri, uri=True, timeout=10)
                    self.logger.debug(f"Successfully connected to database on attempt {attempt + 1}")
                    break
                except sqlite3.Error as e:
                    if attempt < 2:
                        self.logger.debug(f"Connection attempt {attempt + 1} failed: {e}, retrying...")
                        time.sleep(1)
                    else:
                        raise
            
            cursor = conn.cursor()
            
            # Check if cookies table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
            if not cursor.fetchone():
                self.logger.debug("No cookies table found in database")
                return []
                
            query = """
                SELECT host_key, name, value, encrypted_value
                FROM cookies
                WHERE host_key LIKE '%mubi.com%'
            """
            self.logger.debug(f"Executing query: {query}")
            cursor.execute(query)
            
            cookies = []
            for row in cursor.fetchall():
                host_key, name, value, encrypted_value = row
                self.logger.debug(f"Found cookie - Domain: {host_key}, Name: {name}")
                
                # Create a cookie object compatible with browser_cookie3
                cookie = type('Cookie', (), {
                    'domain': host_key,
                    'name': name,
                    'value': value if value else ''  # Use empty string if value is None
                })
                cookies.append(cookie)
                
            conn.close()
            self.logger.debug(f"Successfully extracted {len(cookies)} cookies")
            self.logger.debug(f"Cookie names found: {[c.name for c in cookies]}")
            return cookies
            
        except sqlite3.Error as e:
            self.logger.debug(f"SQLite error reading database: {str(e)}")
            return []
        except Exception as e:
            self.logger.debug(f"Unexpected error reading database: {str(e)}")
            self.logger.exception("Detailed error information:")
            return []

    def _extract_cookies_from_sqlite(self, cookie_path: str) -> List:
        """Extract cookies directly from SQLite database"""
        self.logger.debug(f"Attempting to extract cookies from: {cookie_path}")
        
        if not os.path.exists(cookie_path):
            self.logger.debug(f"Cookie path does not exist: {cookie_path}")
            return []
        
        normalized_path = self.env.normalize_path(cookie_path)
        self.logger.debug(f"Normalized cookie path: {normalized_path}")
        
        try:
            # Try reading directly first
            cookies = self._read_locked_sqlite(normalized_path)
            if cookies:
                return cookies
                
            # If direct read failed, try with a copy as last resort
            temp_dir = tempfile.gettempdir()
            temp_cookie_file = os.path.join(temp_dir, f'mubi_cookies_{os.getpid()}.db')
            self.logger.debug(f"Attempting to copy to temp file: {temp_cookie_file}")
            
            try:
                shutil.copy2(normalized_path, temp_cookie_file)
                cookies = self._read_locked_sqlite(temp_cookie_file)
                return cookies
            except Exception as e:
                self.logger.debug(f"Failed to copy cookie file: {str(e)}")
                return []
            finally:
                if os.path.exists(temp_cookie_file):
                    try:
                        os.remove(temp_cookie_file)
                    except:
                        pass
                        
        except Exception as e:
            self.logger.debug(f"Failed to extract cookies from {normalized_path}: {str(e)}")
            return []

    def _extract_firefox_cookies(self, profile_path: str) -> List:
        """Extract cookies from Firefox profiles"""
        self.logger.debug(f"Searching for Firefox cookies in: {profile_path}")
        cookie_files = []
        
        # Find all profiles
        if os.path.exists(profile_path):
            if os.path.isfile(os.path.join(profile_path, 'cookies.sqlite')):
                cookie_files.append(os.path.join(profile_path, 'cookies.sqlite'))
            else:
                # Search in profile directories
                try:
                    for item in os.listdir(profile_path):
                        full_path = os.path.join(profile_path, item)
                        if os.path.isdir(full_path):
                            cookie_file = os.path.join(full_path, 'cookies.sqlite')
                            if os.path.exists(cookie_file):
                                cookie_files.append(cookie_file)
                except Exception as e:
                    self.logger.debug(f"Error reading Firefox profiles: {str(e)}")
        
        self.logger.debug(f"Found Firefox cookie files: {cookie_files}")
        
        cookies = []
        for cookie_file in cookie_files:
            try:
                new_cookies = self._extract_cookies_from_sqlite(cookie_file)
                cookies.extend(new_cookies)
            except Exception as e:
                self.logger.debug(f"Failed to extract cookies from {cookie_file}: {str(e)}")
                
        return cookies

    def _load_cookie_file(self, cookie_path: str) -> List:
        """Load cookies from a Netscape/Mozilla format cookies.txt file"""
        self.logger.debug(f"Loading cookie file: {cookie_path}")
        
        if not os.path.exists(cookie_path):
            raise FileNotFoundError(f"Cookie file not found: {cookie_path}")
            
        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            cookies = []
            for line in content.split('\n'):
                if line and not line.startswith('#'):
                    fields = line.strip().split('\t')
                    if len(fields) >= 7:
                        cookie = type('Cookie', (), {
                            'domain': fields[0],
                            'name': fields[5],
                            'value': fields[6]
                        })
                        cookies.append(cookie)
                        self.logger.debug(f"Loaded cookie - Domain: {fields[0]}, Name: {fields[5]}")
            return cookies
        except Exception as e:
            raise ValueError(f"Failed to parse cookie file: {str(e)}")

    def get_browser_cookies(self) -> List:
        """
        Get cookies from the selected browser or cookie file.
        Uses environment-specific methods for cookie extraction.
        
        Returns:
            List: List of browser cookies
        
        Raises:
            ValueError: If browser is not supported
            Exception: If cookie extraction fails
        """
        cookies = []
        cookie_paths = self.env.get_browser_cookie_paths(self.browser_name)
        
        # Try direct SQLite extraction first
        if self.browser_name == 'firefox':
            for path in cookie_paths:
                if os.path.exists(path):
                    try:
                        new_cookies = self._extract_firefox_cookies(path)
                        if new_cookies:
                            cookies.extend(new_cookies)
                    except Exception as e:
                        self.logger.debug(f"Failed to extract Firefox cookies from {path}: {str(e)}")
        else:  # Chrome or Edge
            for path in cookie_paths:
                if os.path.exists(path):
                    try:
                        new_cookies = self._extract_cookies_from_sqlite(path)
                        if new_cookies:
                            cookies.extend(new_cookies)
                    except Exception as e:
                        self.logger.debug(f"Failed to extract cookies from {path}: {str(e)}")
        
        # Try browser_cookie3 only if we have admin rights
        if not cookies and is_admin():
            self.logger.debug("No cookies found via direct extraction, trying browser_cookie3")
            try:
                browser_func = {
                    'chrome': browser_cookie3.chrome,
                    'firefox': browser_cookie3.firefox,
                    'edge': browser_cookie3.edge
                }.get(self.browser_name)
                
                if browser_func:
                    try:
                        self.logger.debug("Attempting browser_cookie3 fallback")
                        cookies = browser_func()
                        self.logger.debug(f"Found {len(cookies) if cookies else 0} cookies via browser_cookie3")
                    except Exception as e:
                        self.logger.debug(f"browser_cookie3 fallback failed: {str(e)}")
                
            except Exception as e:
                self.logger.debug(f"Failed to initialize browser_cookie3: {str(e)}")
        
        if not cookies:
            raise Exception("No cookies found")
            
        return cookies

    def _validate_token(self, auth_token: str, dt_custom_data: str) -> bool:
        """Validate authentication tokens"""
        self.logger.debug("Validating authentication tokens")
        
        if not auth_token or not dt_custom_data:
            self.logger.debug("Missing token or custom data")
            return False
            
        try:
            # Validate dt-custom-data format (should be base64 encoded JSON)
            custom_data = json.loads(base64.b64decode(dt_custom_data))
            required_fields = ['userId', 'sessionId', 'merchant']
            valid = all(field in custom_data for field in required_fields)
            self.logger.debug(f"Token validation result: {valid}")
            return valid
        except Exception as e:
            self.logger.debug(f"Token validation failed: {str(e)}")
            return False

    

    def _prompt_authentication_method(self) -> Tuple[Dict[str, str], bool]:
        """
        Prompt user to choose an authentication method
        Returns tuple of (headers, success)
        """
        self.logger.debug("Prompting user for authentication method")
        
        print("\nAuthentication failed. Please choose an authentication method:")
        print("1. Enter path to cookies.txt file")
        print("2. Enter authentication tokens manually")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-2): ").strip()
                if choice == "1":
                    path = input("\nEnter path to cookies.txt file: ").strip()
                    try:
                        cookies = self._load_cookie_file(path)
                        auth_data = self._extract_auth_from_cookies(cookies)
                        if auth_data:
                            self.logger.debug("Successfully loaded auth from cookie file")
                            return auth_data, True
                    except Exception as e:
                        print(f"\nError loading cookie file: {str(e)}")
                        continue
                        
                elif choice == "2":
                    print("\nTo get these tokens:")
                    print("1. Log in to mubi.com in your browser")
                    print("2. Open Developer Tools (F12)")
                    print("3. Go to Network tab")
                    print("4. Refresh the page")
                    print("5. Look for any API request to api.mubi.com")
                    print("6. In the request headers, find:")
                    print("   - Authorization (starts with 'Bearer')")
                    print("   - dt-custom-data\n")
                    
                    auth_token = input("Enter the Bearer token (without 'Bearer' prefix): ").strip()
                    dt_custom_data = input("Enter the dt-custom-data value: ").strip()
                    
                    if self._validate_token(auth_token, dt_custom_data):
                        self.logger.debug("Successfully validated manual token input")
                        return {
                            'Authorization': f'Bearer {auth_token}',
                            'dt-custom-data': dt_custom_data
                        }, True
                    else:
                        print("\nInvalid authentication tokens provided.")
                        continue
                else:
                    print("\nInvalid choice. Please enter 1 or 2.")
                    continue
            except KeyboardInterrupt:
                return {}, False
                
        return {}, False

    def _extract_auth_from_cookies(self, cookies: List) -> Dict[str, str]:
        """Extract authentication headers from cookies"""
        self.logger.debug(f"Extracting auth from {len(cookies)} cookies")
        
        auth_token = None
        dt_custom_data = None
        
        for cookie in cookies:
            if hasattr(cookie, 'domain') and cookie.domain == 'mubi.com':
                if cookie.name == "authToken":
                    auth_token = cookie.value
                    self.logger.debug("Found authToken cookie")
                elif cookie.name == "dtCustomData":
                    dt_custom_data = cookie.value
                    self.logger.debug("Found dtCustomData cookie")
        
        if self._validate_token(auth_token, dt_custom_data):
            self.logger.debug("Successfully extracted valid auth headers")
            return {
                'Authorization': f'Bearer {auth_token}',
                'dt-custom-data': dt_custom_data
            }
        return {}

    def generate_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers using available methods.
        Attempts cookie extraction first, then falls back to browser launch or manual input.
        
        Returns:
            dict: Dictionary containing authentication headers

        Raises:
            Exception: If all authentication methods fail
        """
        headers = None
        errors = []
        
        self.logger.debug(f"Environment: {self.env.os_type}, Browser: {self.browser_name}, GUI capable: {self.env.gui_capable}")
        
        # Try cookie extraction first
        try:
            self.logger.debug("Attempting cookie extraction")
            cookies = self.get_browser_cookies()
            self.logger.debug(f"Found {len(cookies)} cookies")
            
            headers = self._extract_auth_from_cookies(cookies)
            if headers:
                self.logger.info("Successfully generated headers from browser cookies")
                return headers
                
            self.logger.debug("No valid auth headers found in cookies")
        except Exception as e:
            errors.append(f"Cookie extraction failed: {str(e)}")
            self.logger.error(f"Cookie extraction error: {str(e)}")

        # If cookie extraction failed and we have GUI capability, try browser launch
        if not headers and self.env.gui_capable:
            try:
                self.logger.info("Attempting browser authentication...")
                self.logger.debug("Using Mubi login page URL: https://mubi.com/login")
                if self.env.launch_browser("https://mubi.com/login"):
                    self.logger.debug("Waiting for user to log in...")
                    input("\nPlease log in to Mubi in your browser and press Enter when done...")
                    
                    # Wait a moment for cookies to be saved
                    self.logger.debug("Waiting for cookies to be saved...")
                    import time
                    time.sleep(2)  # Give browser time to save cookies
                    
                    try:
                        self.logger.debug("Attempting to get cookies after browser login")
                        cookies = self.get_browser_cookies()
                        self.logger.debug(f"Found {len(cookies)} cookies after login")
                        self.logger.debug(f"Cookie names: {[c.name for c in cookies if hasattr(c, 'name')]}")
                        
                        headers = self._extract_auth_from_cookies(cookies)
                        if headers:
                            self.logger.info("Successfully generated headers after browser login")
                            self.logger.debug(f"Auth token length: {len(headers.get('Authorization', ''))}")
                            return headers
                        self.logger.debug("No valid auth headers found after browser login")
                    except Exception as e:
                        errors.append(f"Cookie extraction after login failed: {str(e)}")
                        self.logger.error(f"Post-login cookie extraction error: {str(e)}")
                        self.logger.exception("Detailed cookie extraction error:")
                else:
                    self.logger.error("Failed to launch browser")
                    if not self.env.gui_capable:
                        self.logger.debug("Browser launch failed - no GUI environment detected")
            except Exception as e:
                errors.append(f"Browser authentication failed: {str(e)}")
                self.logger.error(f"Browser launch error: {str(e)}")
                self.logger.exception("Detailed browser launch error:")

        # Last resort: prompt for authentication method
        if not headers:
            self.logger.debug("Attempting manual authentication")
            headers, success = self._prompt_authentication_method()
            if success:
                self.logger.info("Successfully authenticated manually")
                return headers
            self.logger.debug("Manual authentication cancelled or failed")
                
        # If we get here, all methods failed
        error_msg = "\n".join(errors)
        self.logger.error(f"All authentication methods failed:\n{error_msg}")
        raise Exception(f"All authentication methods failed:\n{error_msg}")
