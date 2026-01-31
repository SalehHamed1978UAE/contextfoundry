"""
Text Sanitization Utilities

This module provides general-purpose text sanitization functions to ensure
text data is safe for database storage and consistent processing.

The sanitize_text function is designed to be called at the storage boundary
(before inserting into PostgreSQL) to guarantee database compatibility.
"""

import re
from typing import Optional


def sanitize_text(text: str, remove_control_chars: bool = True) -> str:
    """
    Sanitize text by removing problematic characters for database storage.
    
    This function removes:
    - NUL (0x00) characters: PostgreSQL cannot store these in text columns
    - Optionally other ASCII control characters (0x01-0x1F, 0x7F) except:
      - Newline (0x0A)
      - Carriage return (0x0D)
      - Tab (0x09)
    
    Args:
        text: The text to sanitize
        remove_control_chars: If True, removes all problematic control characters.
                             If False, only removes NUL (0x00) characters.
    
    Returns:
        Sanitized text safe for PostgreSQL storage.
    
    Example:
        >>> sanitize_text("Hello\\x00World")
        'HelloWorld'
        >>> sanitize_text("Line1\\nLine2\\x00End")
        'Line1\\nLine2End'
    """
    if not text:
        return text
    
    # Always remove NUL characters - PostgreSQL cannot store these
    sanitized = text.replace('\x00', '')
    
    if remove_control_chars:
        # Remove other problematic control characters but preserve:
        # - \t (tab, 0x09)
        # - \n (newline, 0x0A)
        # - \r (carriage return, 0x0D)
        # Pattern matches control chars 0x01-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F
        # This is: [\x01-\x08\x0B\x0C\x0E-\x1F\x7F]
        sanitized = re.sub(r'[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sanitized)
    
    return sanitized


def contains_nul_characters(text: str) -> bool:
    """
    Check if text contains NUL characters.
    
    Useful for validation and debugging.
    
    Args:
        text: The text to check
        
    Returns:
        True if text contains NUL (0x00) characters, False otherwise.
    """
    if not text:
        return False
    return '\x00' in text


def sanitize_dict_values(data: dict, keys: Optional[list] = None) -> dict:
    """
    Recursively sanitize string values in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        keys: If provided, only sanitize these keys. If None, sanitize all string values.
    
    Returns:
        New dictionary with sanitized string values.
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            if keys is None or key in keys:
                result[key] = sanitize_text(value)
            else:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = sanitize_dict_values(value, keys)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict_values(item, keys) if isinstance(item, dict)
                else sanitize_text(item) if isinstance(item, str) and (keys is None or key in keys)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result
