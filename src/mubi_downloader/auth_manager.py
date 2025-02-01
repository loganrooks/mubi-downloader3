#!/usr/bin/env python3
import os
import sys
import logging
import browser_cookie3

class AuthManager:
    """
    Manages authentication and cookie extraction for the Mubi downloader.
    Supports multiple browsers and provides error handling for authentication failures.
    """
    
    def __init__(self, browser_name='chrome'):
        """
        Initialize AuthManager with specified browser.
        
        Args:
            browser_name (str): Name of the browser to extract cookies from ('chrome', 'firefox', or 'edge')
        """
        self.browser_name = browser_name.lower()
        self.logger = self._setup_logging()
        self.supported_browsers = {
            'chrome': browser_cookie3.chrome,
            'firefox': browser_cookie3.firefox,
            'edge': browser_cookie3.edge
        }

    def _setup_logging(self):
        """
        Sets up logging configuration for the auth manager.
        
        Returns:
            logging.Logger: Configured logger instance
        """
        logger = logging.getLogger('AuthManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def get_browser_cookies(self):
        """
        Retrieves cookies from the specified browser.
        
        Returns:
            CookieJar: Browser cookie jar containing authentication cookies
            
        Raises:
            ValueError: If browser is not supported
            Exception: If cookie extraction fails
        """
        if self.browser_name not in self.supported_browsers:
            raise ValueError(f"Unsupported browser. Please choose from: {', '.join(self.supported_browsers.keys())}")
        
        try:
            cookies = self.supported_browsers[self.browser_name]()
            if not cookies:
                raise Exception("No cookies found")
            return cookies
        except Exception as e:
            self.logger.error(f"Failed to load cookies from {self.browser_name}: {str(e)}")
            raise Exception(f"Cookie extraction failed: {str(e)}")

    def generate_headers(self):
        """
        Generates authentication headers from browser cookies.
        
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
                self.logger.error("Required cookies not found")
                raise Exception("Authentication cookies not found. Please log in to Mubi in your browser first.")

            headers = {
                "Authorization": f"Bearer {auth_token}",
                "dt-custom-data": dt_custom_data
            }
            
            self.logger.info("Successfully generated authentication headers")
            return headers

        except Exception as e:
            self.logger.error(f"Header generation failed: {str(e)}")
            raise

def main():
    """
    Command-line interface for testing authentication.
    """
    if len(sys.argv) < 2:
        print("Usage: python3 auth_manager.py [browser]")
        sys.exit(1)

    try:
        auth = AuthManager(sys.argv[1])
        headers = auth.generate_headers()
        print("Authentication successful! Headers:")
        for k, v in headers.items():
            # Mask sensitive data in output
            masked_value = v[:10] + "..." if len(v) > 10 else v
            print(f"{k}: {masked_value}")
    except Exception as ex:
        print(f"Error: {ex}")
        sys.exit(1)

if __name__ == "__main__":
    main()
