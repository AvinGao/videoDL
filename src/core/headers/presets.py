"""User-Agent presets for different browsers."""

class UserAgentPresets:
    """Collection of common User-Agent strings."""
    
    @staticmethod
    def chrome_windows() -> str:
        """Chrome on Windows."""
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    @staticmethod
    def chrome_mac() -> str:
        """Chrome on macOS."""
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    @staticmethod
    def chrome_linux() -> str:
        """Chrome on Linux."""
        return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    @staticmethod
    def firefox_windows() -> str:
        """Firefox on Windows."""
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    
    @staticmethod
    def firefox_mac() -> str:
        """Firefox on macOS."""
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0"
    
    @staticmethod
    def safari_mac() -> str:
        """Safari on macOS."""
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
    
    @staticmethod
    def safari_iphone() -> str:
        """Safari on iPhone."""
        return "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
    
    @staticmethod
    def edge_windows() -> str:
        """Edge on Windows."""
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    
    @staticmethod
    def get_default() -> str:
        """Get default User-Agent."""
        return UserAgentPresets.chrome_windows()
    
    @staticmethod
    def get_all() -> dict:
        """Get all User-Agent presets."""
        return {
            "chrome_windows": UserAgentPresets.chrome_windows(),
            "chrome_mac": UserAgentPresets.chrome_mac(),
            "chrome_linux": UserAgentPresets.chrome_linux(),
            "firefox_windows": UserAgentPresets.firefox_windows(),
            "firefox_mac": UserAgentPresets.firefox_mac(),
            "safari_mac": UserAgentPresets.safari_mac(),
            "safari_iphone": UserAgentPresets.safari_iphone(),
            "edge_windows": UserAgentPresets.edge_windows(),
        }