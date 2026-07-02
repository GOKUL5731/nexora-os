"""
Authentication and authorization module
Provides API key-based authentication and role-based authorization
"""
import hashlib
import os
import secrets
from dataclasses import dataclass
from typing import Optional, Set


@dataclass(slots=True)
class User:
    """User information"""
    username: str
    api_key: str
    roles: Set[str]
    created_at: float


class AuthManager:
    """Authentication and authorization manager"""
    
    def __init__(self, config_file: Optional[str] = None) -> None:
        """
        Initialize auth manager
        
        Args:
            config_file: Path to auth config file (optional)
        """
        self.users: dict[str, User] = {}
        self.api_keys: dict[str, str] = {}  # api_key -> username mapping
        self.config_file = config_file
        
        # Load default admin user if no config file
        if not config_file or not os.path.exists(config_file):
            self._add_default_admin()
    
    def _add_default_admin(self) -> None:
        """Add default admin user with generated API key"""
        api_key = self.generate_api_key()
        admin_user = User(
            username="admin",
            api_key=api_key,
            roles={"admin", "user"},
            created_at=0.0
        )
        self.users["admin"] = admin_user
        self.api_keys[api_key] = "admin"
    
    def generate_api_key(self) -> str:
        """Generate a secure API key"""
        return secrets.token_urlsafe(32)
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def add_user(self, username: str, roles: Set[str], api_key: Optional[str] = None) -> str:
        """
        Add a new user
        
        Args:
            username: Username
            roles: Set of roles
            api_key: API key (optional, will generate if not provided)
            
        Returns:
            API key for the user
        """
        if username in self.users:
            raise ValueError(f"User {username} already exists")
        
        if api_key is None:
            api_key = self.generate_api_key()
        
        user = User(
            username=username,
            api_key=api_key,
            roles=roles,
            created_at=0.0
        )
        
        self.users[username] = user
        self.api_keys[api_key] = username
        
        return api_key
    
    def remove_user(self, username: str) -> bool:
        """
        Remove a user
        
        Args:
            username: Username to remove
            
        Returns:
            True if user was removed, False otherwise
        """
        if username not in self.users:
            return False
        
        user = self.users[username]
        del self.api_keys[user.api_key]
        del self.users[username]
        
        return True
    
    def authenticate(self, api_key: str) -> Optional[User]:
        """
        Authenticate user by API key
        
        Args:
            api_key: API key to authenticate
            
        Returns:
            User if authentication successful, None otherwise
        """
        username = self.api_keys.get(api_key)
        if username is None:
            return None
        
        return self.users.get(username)
    
    def authorize(self, user: User, required_role: str) -> bool:
        """
        Check if user has required role
        
        Args:
            user: User to check
            required_role: Required role
            
        Returns:
            True if user has required role, False otherwise
        """
        if "admin" in user.roles:
            return True
        
        return required_role in user.roles
    
    def get_user(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.users.get(username)
    
    def list_users(self) -> list[dict]:
        """List all users (without API keys)"""
        return [
            {
                "username": user.username,
                "roles": list(user.roles),
                "created_at": user.created_at
            }
            for user in self.users.values()
        ]
    
    def rotate_api_key(self, username: str) -> str:
        """
        Rotate API key for a user
        
        Args:
            username: Username
            
        Returns:
            New API key
        """
        if username not in self.users:
            raise ValueError(f"User {username} not found")
        
        user = self.users[username]
        old_api_key = user.api_key
        
        # Remove old API key mapping
        del self.api_keys[old_api_key]
        
        # Generate new API key
        new_api_key = self.generate_api_key()
        user.api_key = new_api_key
        
        # Add new mapping
        self.api_keys[new_api_key] = username
        
        return new_api_key


# Global auth manager instance
global_auth_manager = AuthManager()


def authenticate_request(api_key: str) -> Optional[User]:
    """
    Authenticate a request by API key
    
    Args:
        api_key: API key from request
        
    Returns:
        User if authenticated, None otherwise
    """
    return global_auth_manager.authenticate(api_key)


def authorize_request(user: User, required_role: str) -> bool:
    """
    Authorize a request by role
    
    Args:
        user: Authenticated user
        required_role: Required role
        
    Returns:
        True if authorized, False otherwise
    """
    return global_auth_manager.authorize(user, required_role)


def get_default_admin_api_key() -> str:
    """Get the default admin API key"""
    admin_user = global_auth_manager.get_user("admin")
    if admin_user:
        return admin_user.api_key
    return ""
