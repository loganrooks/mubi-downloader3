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
from typing import List, Dict, Optional, Tuple, Any, Union
from http.cookiejar import CookieJar
import browser_cookie3
from .environment import EnvironmentDetector



def is_admin() -> bool:
    """Check if running with admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

class Cookie:
    """Simple cookie data class"""
    def __init__(self, domain: str, name: str, value: str, **kwargs):
        self.domain = domain
        self.name = name
        self.value = value
        for k, v in kwargs.items():
            setattr(self, k, v)

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
        self.auth_token: Optional[str] = None
        self.dt_custom_data: Optional[str] = None
        
        self.logger.debug(f"Initialized AuthManager for browser: {browser_name}")
        self.logger.debug(f"Running as admin: {is_admin()}")
        self.logger.debug(f"Environment type: {self.env.os_type}")
        self.logger.debug(f"GUI capable: {self.env.gui_capable}")
        
    def _decrypt_chrome_cookies(self, encrypted_value: bytes) -> str:
        """Decrypt Chrome/Edge cookie value"""
        if not encrypted_value:
            return ""
            
        try:
            if os.name == 'nt':
                import win32crypt
                try:
                    decrypted = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1]
                    if decrypted:
                        return decrypted.decode()
                except Exception as e:
                    self.logger.debug(f"Windows CryptUnprotectData failed: {e}")
                    
            # Try local state key decryption (newer Chrome/Edge versions)
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                
                def get_encryption_key() -> Optional[bytes]:
                    local_state_path = None
                    if self.browser_name == 'chrome':
                        local_state_path = os.path.expandvars('%LocalAppData%\\Google\\Chrome\\User Data\\Local State')
                    elif self.browser_name == 'edge':
                        local_state_path = os.path.expandvars('%LocalAppData%\\Microsoft\\Edge\\User Data\\Local State')
                        
                    if local_state_path and os.path.exists(local_state_path):
                        with open(local_state_path, 'r', encoding='utf-8') as f:
                            local_state = json.loads(f.read())
                            key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
                            key = key[5:] # Remove 'DPAPI' prefix
                            return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
                    return None
                    
                if len(encrypted_value) > 15:
                    key = get_encryption_key()
                    if key:
                        nonce = encrypted_value[3:15]
                        cipher = AESGCM(key)
                        try:
                            decrypted = cipher.decrypt(nonce, encrypted_value[15:], None)
                            return decrypted.decode()
                        except Exception as e:
                            self.logger.debug(f"AES-GCM decryption failed: {e}")
                            
            except ImportError:
                self.logger.debug("cryptography module not available for AES-GCM decryption")
                
        except ImportError:
            self.logger.debug("win32crypt not available")
            
        return ""

    def _read_locked_sqlite(self, db_path: str, max_retries: int = 3) -> List[Cookie]:
        """Read cookies from a potentially locked SQLite database"""
        self.logger.debug(f"Attempting to read SQLite database: {db_path}")
        
        if not os.path.exists(db_path):
            self.logger.debug(f"Database file does not exist: {db_path}")
            return []
            
        self.logger.debug(f"Database file size: {os.path.getsize(db_path)} bytes")
        self.logger.debug(f"Last modified: {os.path.getmtime(db_path)}")
        
        cookies = []
        errors = []
        
        for attempt in range(max_retries):
            if attempt > 0:
                self.logger.debug(f"Retry attempt {attempt + 1} of {max_retries}")
                time.sleep(2)  # Wait before retry
                
            temp_path = None
            try:
                # Method 1: Copy to temp and read
                temp_path = os.path.join(tempfile.gettempdir(), f'mubi_cookies_{os.getpid()}_{attempt}.db')
                shutil.copy2(db_path, temp_path)
                self.logger.debug(f"Copied database to: {temp_path}")
                
                conn = sqlite3.connect(temp_path)
                cookies = self._extract_cookies_from_connection(conn)
                if cookies:
                    return cookies
            except Exception as e:
                self.logger.debug(f"Attempt {attempt + 1} failed: {e}")
                errors.append(str(e))
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
        
        # If all attempts failed, raise error with details
        error_msg = "\n".join(errors)
        raise Exception(f"Failed to read database after {max_retries} attempts:\n{error_msg}")

    def _extract_cookies_from_connection(self, conn: sqlite3.Connection) -> List[Cookie]:
        """Extract and decrypt cookies from an open database connection"""
        try:
            cursor = conn.cursor()
            
            # Check if cookies table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'")
            if not cursor.fetchone():
                self.logger.debug("No cookies table found in database")
                return []
                
            # Get all possible cookie fields
            # First try to find auth tokens directly
            auth_query = """
                SELECT name, value, encrypted_value
                FROM cookies
                WHERE host_key LIKE '%.mubi.com'
                AND name IN ('authToken', 'dtCustomData')
            """
            self.logger.debug("Executing auth query")
            cursor.execute(auth_query)
            found_auth = False
            found_dt = False

            for name, value, encrypted_value in cursor.fetchall():
                if not value and encrypted_value:
                    self.logger.debug(f"Found encrypted auth cookie: {name}")
                    value = self._decrypt_chrome_cookies(encrypted_value)
                    
                if value:
                    if name == 'authToken':
                        self.auth_token = value
                        found_auth = True
                        self.logger.debug("Found authToken")
                    elif name == 'dtCustomData':
                        self.dt_custom_data = value
                        found_dt = True
                        self.logger.debug("Found dtCustomData")

            self.logger.debug(f"Auth token found: {found_auth}, dt-custom-data found: {found_dt}")

            # Now get all cookies for the domain
            query = """
                SELECT host_key, name, value, encrypted_value, is_secure,
                       path, expires_utc, is_httponly
                FROM cookies
                WHERE host_key LIKE '%.mubi.com' OR host_key = 'mubi.com'
            """
            self.logger.debug("Executing cookie query")
            cursor.execute(query)
            
            cookies = []
            for row in cursor.fetchall():
                try:
                    host_key, name, value, encrypted_value, is_secure = row[:5]
                    path, expires_utc, is_httponly = row[5:8]
                    
                    if not value and encrypted_value:
                        self.logger.debug(f"Found encrypted cookie: {name}")
                        value = self._decrypt_chrome_cookies(encrypted_value)
                            
                    if value:
                        domain = host_key.lstrip('.')
                        self.logger.debug(f"Processing cookie - Domain: {domain}, Name: {name}")
                        cookie = Cookie(
                            domain=domain,
                            name=name,
                            value=value,
                            secure=bool(is_secure),
                            path=path,
                            expires=expires_utc,
                            httponly=bool(is_httponly)
                        )
                        cookies.append(cookie)
                    else:
                        self.logger.debug(f"Skipping cookie with no value - Name: {name}")
                        
                except Exception as e:
                    self.logger.debug(f"Failed to process cookie row: {e}")
                    continue
                    
            conn.close()
            self.logger.debug(f"Successfully extracted {len(cookies)} cookies")
            if cookies:
                self.logger.debug(f"Cookie names found: {[c.name for c in cookies]}")
                self.logger.debug(f"Cookie domains found: {[c.domain for c in cookies]}")
            return cookies
            
        except Exception as e:
            self.logger.debug(f"Failed to extract cookies from connection: {e}")
            self.logger.exception("Detailed error information:")
            try:
                conn.close()
            except:
                pass
            return []

    def _extract_cookies_from_sqlite(self, cookie_path: str) -> List[Cookie]:
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

    def _extract_firefox_cookies(self, profile_path: str) -> List[Cookie]:
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

    def _load_cookie_file(self, cookie_path: str) -> List[Cookie]:
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
                        cookie = Cookie(
                            domain=fields[0],
                            name=fields[5],
                            value=fields[6]
                        )
                        cookies.append(cookie)
                        self.logger.debug(f"Loaded cookie - Domain: {fields[0]}, Name: {fields[5]}")
            return cookies
        except Exception as e:
            raise ValueError(f"Failed to parse cookie file: {str(e)}")

    def _convert_browser_cookie3_cookies(self, cookies: Union[CookieJar, List]) -> List[Cookie]:
        """Convert browser_cookie3 CookieJar or list to our Cookie objects"""
        result = []
        try:
            for cookie in cookies:
                try:
                    # Convert from browser_cookie3 Cookie to our Cookie
                    domain = str(getattr(cookie, 'domain', ''))
                    name = str(getattr(cookie, 'name', ''))
                    value = str(getattr(cookie, 'value', ''))
                    
                    # Skip invalid cookies
                    if not domain or not name or not value:
                        self.logger.debug(f"Skipping invalid cookie: {cookie}")
                        continue
                        
                    result.append(Cookie(
                        domain=domain,
                        name=name,
                        value=value,
                        secure=bool(getattr(cookie, 'secure', False)),
                        path=str(getattr(cookie, 'path', '/')),
                        expires=getattr(cookie, 'expires', None),
                        httponly=bool(getattr(cookie, 'httponly', False))
                    ))
                except Exception as e:
                    self.logger.debug(f"Failed to convert cookie: {e}")
            self.logger.debug(f"Successfully converted {len(result)} cookies")
        except Exception as e:
            self.logger.debug(f"Error converting browser_cookie3 cookies: {e}")
        return result

    def get_browser_cookies(self) -> List[Cookie]:
        """
        Get cookies from the selected browser or cookie file.
        Uses environment-specific methods for cookie extraction.
        
        Returns:
            List[Cookie]: List of Cookie objects extracted from browser or cookie file
        
        Raises:
            ValueError: If browser is not supported
            Exception: If cookie extraction fails
        """
        cookies = []
        self.logger.debug("Starting cookie extraction")
        cookie_paths = self.env.get_browser_cookie_paths(self.browser_name)
        
        # Try direct SQLite extraction first (one attempt)
        if self.browser_name == 'firefox':
            for path in cookie_paths:
                if os.path.exists(path):
                    try:
                        new_cookies = self._extract_firefox_cookies(path)
                        if new_cookies:
                            cookies.extend(new_cookies)
                            self.logger.debug(f"Successfully extracted {len(new_cookies)} Firefox cookies")
                            break  # Found cookies, stop searching
                    except Exception as e:
                        self.logger.debug(f"Failed to extract Firefox cookies from {path}: {str(e)}")
        else:  # Chrome or Edge
            default_cookie_path = next((p for p in cookie_paths if "Default" in p), None)
            if default_cookie_path and os.path.exists(default_cookie_path):
                try:
                    new_cookies = self._extract_cookies_from_sqlite(default_cookie_path)
                    if new_cookies:
                        cookies.extend(new_cookies)
                        self.logger.debug(f"Successfully extracted {len(new_cookies)} cookies from Default profile")
                except Exception as e:
                    self.logger.debug(f"Failed to extract cookies from Default profile: {str(e)}")
        
        # Try browser_cookie3 as fallback regardless of admin rights
        if not cookies:
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
                        browser_cookies = browser_func(domain_name='mubi.com')  # Only get mubi.com cookies
                        if browser_cookies:
                            cookies = self._convert_browser_cookie3_cookies(browser_cookies)
                            self.logger.debug(f"Found {len(cookies)} cookies via browser_cookie3")
                    except Exception as e:
                        self.logger.debug(f"browser_cookie3 fallback failed: {str(e)}")
                        self.logger.exception("Detailed browser_cookie3 error:")
                
            except Exception as e:
                self.logger.debug(f"Failed to initialize browser_cookie3: {str(e)}")
        
        if not cookies:
            raise Exception("No cookies found")
            
        return cookies

    def _validate_token(self, auth_token: str, dt_custom_data: str) -> tuple[bool, Optional[Dict[str, str]]]:
        """
        Validate authentication tokens and return formatted headers if valid
        Returns tuple of (is_valid, formatted_headers)
        """
        self.logger.debug("Validating authentication tokens")
        
        if not auth_token or not dt_custom_data:
            self.logger.debug("Missing token or custom data")
            return False, None
            
        try:
            # Clean up auth token
            auth_token = auth_token.strip()
            if auth_token.lower().startswith('bearer '):
                auth_token = auth_token[7:]
            elif auth_token.lower().startswith('bearer'):
                auth_token = auth_token[6:]
                
            # First try base64 decode of dt-custom-data
            try:
                custom_data = json.loads(base64.b64decode(dt_custom_data))
                self.logger.debug("Successfully decoded base64 dt-custom-data")
            except Exception as e:
                self.logger.debug(f"Failed base64 decode: {e}, trying plain JSON")
                try:
                    # Try direct JSON parse
                    custom_data = json.loads(dt_custom_data)
                    # Re-encode as base64
                    dt_custom_data = base64.b64encode(json.dumps(custom_data).encode()).decode()
                    self.logger.debug("Successfully parsed plain JSON dt-custom-data")
                except Exception as e2:
                    self.logger.debug(f"JSON parse failed: {e2}")
                    return False, None
            
            # Validate required fields in custom data
            required_fields = ['userId', 'sessionId', 'merchant']
            if not all(field in custom_data for field in required_fields):
                self.logger.debug(f"Missing required fields. Found: {list(custom_data.keys())}")
                return False, None
            
            # Format headers
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'dt-custom-data': dt_custom_data
            }
            
            self.logger.debug("Successfully validated and formatted tokens")
            self.logger.debug(f"Auth token length: {len(auth_token)}")
            self.logger.debug(f"DT custom data fields: {list(custom_data.keys())}")
            self.logger.debug(f"Generated headers: {headers}")
            
            return True, headers
            
        except Exception as e:
            self.logger.debug(f"Token validation failed: {str(e)}")
            self.logger.exception("Detailed validation error:")
            return False, None

    

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
                    print("6. In the request headers, find and copy:")
                    print("   - Authorization (including 'Bearer' prefix)")
                    print("   - dt-custom-data\n")
                    
                    auth_token = input("Enter the complete Authorization header value: ").strip()
                    dt_custom_data = input("Enter the dt-custom-data value: ").strip()
                    
                    # Clean up auth token if needed
                    if not auth_token.lower().startswith('bearer '):
                        auth_token = f"Bearer {auth_token}"
                    
                    valid, headers = self._validate_token(auth_token.replace('Bearer ', ''), dt_custom_data)
                    if valid and headers:
                        self.logger.debug("Successfully validated manual token input")
                        self.logger.debug(f"Generated headers: {headers}")
                        return headers, True
                    else:
                        print("\nInvalid authentication tokens provided.")
                        continue
                else:
                    print("\nInvalid choice. Please enter 1 or 2.")
                    continue
            except KeyboardInterrupt:
                return {}, False
                
        return {}, False

    def _extract_auth_from_cookies(self, cookies: Union[CookieJar, List[Cookie]]) -> Dict[str, str]:
        """Extract authentication headers from cookies"""
        self.logger.debug(f"Extracting auth from {len(cookies)} cookies")
        
        auth_token = None
        dt_custom_data = None
        
        # First try exact domain match
        for cookie in cookies:
            if cookie.domain == 'mubi.com':
                if cookie.name == "authToken":
                    auth_token = cookie.value
                    self.logger.debug("Found authToken cookie")
                elif cookie.name == "dtCustomData":
                    dt_custom_data = cookie.value
                    self.logger.debug("Found dtCustomData cookie")
        
        # If not found, try subdomains
        if not auth_token or not dt_custom_data:
            for cookie in cookies:
                domain = cookie.domain.lstrip('.')
                if any(d in domain for d in ['mubi.com', 'api.mubi.com']):
                    if cookie.name == "authToken" and not auth_token:
                        auth_token = cookie.value
                        self.logger.debug(f"Found authToken cookie on {domain}")
                    elif cookie.name == "dtCustomData" and not dt_custom_data:
                        dt_custom_data = cookie.value
                        self.logger.debug(f"Found dtCustomData cookie on {domain}")
        
        if auth_token and dt_custom_data:
            valid, headers = self._validate_token(auth_token, dt_custom_data)
            if valid and headers:
                self.logger.debug("Successfully validated auth headers")
                return headers
            self.logger.debug("Token validation failed")
        else:
            self.logger.debug("Missing required cookies")
        return {}

    def _extract_headers_from_active_session(self, movie_url: str) -> Optional[Dict[str, str]]:
        """Extract authentication headers from an active browser session streaming a movie"""
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            self.logger.info("Launching browser...")
            options = uc.ChromeOptions()
            options.add_argument('--auto-open-devtools-for-tabs')
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            driver = uc.Chrome(options=options)

            try:
                print("\nA browser window will open with developer tools.")
                print("1. Log in to Mubi if needed")
                print("2. Navigate to the movie page")
                print("3. Press play on the movie")
                print("4. Once the movie starts playing, press Enter here to capture the authentication headers")

                # Navigate to the movie page
                self.logger.debug(f"Navigating to movie page: {movie_url}")
                driver.get(movie_url)
                
                input("\nPress Enter once the movie is playing...")
                
                # Enable network interception
                from selenium.webdriver.support.wait import WebDriverWait
                import time
                start_time = time.time()
                max_wait = 60  # Maximum seconds to wait for auth headers
                
                while time.time() - start_time < max_wait:
                    logs = driver.get_log('performance')
                    for entry in logs:
                        try:
                            message = json.loads(entry.get('message', '{}')).get('message', {})
                            if message.get('method') == 'Network.requestWillBeSent':
                                request = message.get('params', {}).get('request', {})
                                if 'api.mubi.com' in request.get('url', '') and '/viewing/secure_url' in request.get('url', ''):
                                    headers = request.get('headers', {})
                                    if 'Authorization' in headers and 'dt-custom-data' in headers:
                                        self.logger.debug("Found authentication headers in network request")
                                        return {
                                            'Authorization': headers['Authorization'],
                                            'dt-custom-data': headers['dt-custom-data']
                                        }
                        except json.JSONDecodeError:
                            continue
                    time.sleep(1)  # Check every second
                
                self.logger.debug("Could not find authentication headers in network requests")
                return None
                
            finally:
                driver.quit()
                
        except Exception as e:
            self.logger.error(f"Failed to extract headers from active session: {e}")
            self.logger.exception("Detailed error:")
            return None

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

        # If cookie extraction failed and we have GUI capability, try extracting from active session
        if not headers and self.env.gui_capable:
            try:
                print("\nWould you like to extract headers automatically? (y/n)")
                print("This will launch a browser where you can log in and watch the movie.")
                if input().lower().strip() == 'y':
                    print("\nEnter the URL of the movie page (e.g., https://mubi.com/films/movie-name):")
                    movie_url = input().strip()
                    if movie_url:
                        self.logger.info("Attempting to extract headers from active session...")
                        headers = self._extract_headers_from_active_session(movie_url)
                        if headers:
                            self.logger.info("Successfully extracted headers from active session")
                            return headers
                        self.logger.debug("Failed to extract headers from active session")
            except Exception as e:
                errors.append(f"Active session extraction failed: {str(e)}")
                self.logger.error(f"Active session extraction error: {str(e)}")

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