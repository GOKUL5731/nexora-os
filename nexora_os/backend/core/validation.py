"""
Input validation and sanitization module
Provides validation functions for user inputs across the system
"""
import re
from typing import Any, Optional


class ValidationError(Exception):
    """Raised when input validation fails"""
    pass


class InputValidator:
    """Validator for user inputs"""
    
    # Patterns for validation
    SQL_INJECTION_PATTERN = re.compile(
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
        re.IGNORECASE
    )
    XSS_PATTERN = re.compile(
        r"<script.*?>.*?</script>|javascript:|on\w+\s*=|eval\(|expression\(",
        re.IGNORECASE
    )
    PATH_TRAVERSAL_PATTERN = re.compile(r"\.\./|\.\.\\")
    COMMAND_INJECTION_PATTERN = re.compile(r"[;&|`$]")
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 10000) -> str:
        """Sanitize string input"""
        if not isinstance(input_str, str):
            raise ValidationError("Input must be a string")
        
        # Truncate to max length
        if len(input_str) > max_length:
            input_str = input_str[:max_length]
        
        # Remove null bytes
        input_str = input_str.replace("\x00", "")
        
        # Normalize whitespace
        input_str = " ".join(input_str.split())
        
        return input_str
    
    @staticmethod
    def validate_sql_safe(input_str: str) -> bool:
        """Check if input is safe from SQL injection"""
        if not isinstance(input_str, str):
            return False
        
        # Check for SQL keywords
        if InputValidator.SQL_INJECTION_PATTERN.search(input_str):
            return False
        
        return True
    
    @staticmethod
    def validate_xss_safe(input_str: str) -> bool:
        """Check if input is safe from XSS attacks"""
        if not isinstance(input_str, str):
            return False
        
        # Check for XSS patterns
        if InputValidator.XSS_PATTERN.search(input_str):
            return False
        
        return True
    
    @staticmethod
    def validate_path_safe(input_str: str) -> bool:
        """Check if input is safe from path traversal"""
        if not isinstance(input_str, str):
            return False
        
        # Check for path traversal patterns
        if InputValidator.PATH_TRAVERSAL_PATTERN.search(input_str):
            return False
        
        return True
    
    @staticmethod
    def validate_command_safe(input_str: str) -> bool:
        """Check if input is safe from command injection"""
        if not isinstance(input_str, str):
            return False
        
        # Check for command injection patterns
        if InputValidator.COMMAND_INJECTION_PATTERN.search(input_str):
            return False
        
        return True
    
    @staticmethod
    def validate_agent_name(input_str: str) -> bool:
        """Validate agent name (alphanumeric, underscores, hyphens)"""
        if not isinstance(input_str, str):
            return False
        
        pattern = re.compile(r"^[a-zA-Z0-9_-]+$")
        return bool(pattern.match(input_str))
    
    @staticmethod
    def validate_file_path(input_str: str) -> bool:
        """Validate file path (no special characters except path separators)"""
        if not isinstance(input_str, str):
            return False
        
        # Allow alphanumeric, spaces, dots, underscores, hyphens, and path separators
        pattern = re.compile(r"^[a-zA-Z0-9_\-./\\ ]+$")
        return bool(pattern.match(input_str))
    
    @staticmethod
    def validate_url(input_str: str) -> bool:
        """Validate URL format"""
        if not isinstance(input_str, str):
            return False
        
        pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:\S+(?::\S*)?@)?"  # username:password@
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"  # domain
            r"(?:[a-z]{2,})"  # TLD
            r"(?::\d{2,5})?"  # port
            r"(?:/\S*)?$",  # path
            re.IGNORECASE
        )
        return bool(pattern.match(input_str))
    
    @staticmethod
    def validate_json_safe(input_str: str) -> bool:
        """Check if input is safe JSON"""
        if not isinstance(input_str, str):
            return False
        
        try:
            import json
            json.loads(input_str)
            return True
        except json.JSONDecodeError:
            return False
    
    @classmethod
    def validate_input(cls, input_data: Any, validation_type: str = "general") -> tuple[bool, Optional[str]]:
        """
        Validate input based on type
        Returns (is_valid, error_message)
        """
        if input_data is None:
            return True, None
        
        # Handle string inputs
        if isinstance(input_data, str):
            sanitized = cls.sanitize_string(input_data)
            
            if not cls.validate_sql_safe(sanitized):
                return False, "Input contains potentially unsafe SQL patterns"
            
            if not cls.validate_xss_safe(sanitized):
                return False, "Input contains potentially unsafe XSS patterns"
            
            if not cls.validate_command_safe(sanitized):
                return False, "Input contains potentially unsafe command patterns"
            
            return True, None
        
        # Handle dict inputs (JSON-like)
        if isinstance(input_data, dict):
            for key, value in input_data.items():
                is_valid, error = cls.validate_input(key, validation_type)
                if not is_valid:
                    return False, f"Invalid key in dict: {error}"
                
                is_valid, error = cls.validate_input(value, validation_type)
                if not is_valid:
                    return False, f"Invalid value in dict: {error}"
            return True, None
        
        # Handle list inputs
        if isinstance(input_data, list):
            for item in input_data:
                is_valid, error = cls.validate_input(item, validation_type)
                if not is_valid:
                    return False, f"Invalid item in list: {error}"
            return True, None
        
        # Handle other types (numbers, booleans, etc.)
        return True, None


def validate_and_sanitize(input_data: Any, validation_type: str = "general") -> Any:
    """
    Validate and sanitize input data
    Raises ValidationError if validation fails
    """
    is_valid, error_message = InputValidator.validate_input(input_data, validation_type)
    
    if not is_valid:
        raise ValidationError(error_message)
    
    # Sanitize strings
    if isinstance(input_data, str):
        return InputValidator.sanitize_string(input_data)
    
    # Sanitize dict values
    if isinstance(input_data, dict):
        return {
            validate_and_sanitize(k, validation_type): validate_and_sanitize(v, validation_type)
            for k, v in input_data.items()
        }
    
    # Sanitize list items
    if isinstance(input_data, list):
        return [validate_and_sanitize(item, validation_type) for item in input_data]
    
    return input_data
