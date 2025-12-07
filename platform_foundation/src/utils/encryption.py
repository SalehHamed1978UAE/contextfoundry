"""
Encryption utilities for Platform Foundation.

Uses Fernet symmetric encryption for sensitive connector configurations.
"""

import os
import json
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class ConfigEncryption:
    """Handles encryption/decryption of connector configurations."""
    
    def __init__(self):
        key = os.environ.get('FERNET_KEY')
        if not key:
            raise ValueError("FERNET_KEY environment variable is required")
        self._fernet = Fernet(key.encode())
    
    def encrypt_config(self, config: dict) -> bytes:
        """Encrypt a configuration dictionary to bytes."""
        json_str = json.dumps(config)
        return self._fernet.encrypt(json_str.encode())
    
    def decrypt_config(self, encrypted: bytes) -> dict:
        """Decrypt bytes back to configuration dictionary."""
        try:
            decrypted = self._fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except InvalidToken:
            logger.error("Failed to decrypt config - invalid key or corrupted data")
            raise ValueError("Invalid encryption key or corrupted data")
        except json.JSONDecodeError:
            logger.error("Decrypted data is not valid JSON")
            raise ValueError("Decrypted data is not valid JSON")


_encryption_instance = None

def get_encryption() -> ConfigEncryption:
    """Get singleton encryption instance."""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = ConfigEncryption()
    return _encryption_instance
