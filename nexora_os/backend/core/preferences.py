"""
User Preferences and Profiles Module
Manages user settings, preferences, and profiles
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(slots=True)
class UserPreferences:
    """User preferences"""
    language: str = "en"
    voice_enabled: bool = True
    voice_speed: float = 1.0
    voice_pitch: float = 1.0
    theme: str = "dark"
    notifications_enabled: bool = True
    auto_response: bool = False
    privacy_mode: bool = False
    custom_commands: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "language": self.language,
            "voice_enabled": self.voice_enabled,
            "voice_speed": self.voice_speed,
            "voice_pitch": self.voice_pitch,
            "theme": self.theme,
            "notifications_enabled": self.notifications_enabled,
            "auto_response": self.auto_response,
            "privacy_mode": self.privacy_mode,
            "custom_commands": self.custom_commands,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserPreferences":
        """Create from dictionary"""
        return cls(
            language=data.get("language", "en"),
            voice_enabled=data.get("voice_enabled", True),
            voice_speed=data.get("voice_speed", 1.0),
            voice_pitch=data.get("voice_pitch", 1.0),
            theme=data.get("theme", "dark"),
            notifications_enabled=data.get("notifications_enabled", True),
            auto_response=data.get("auto_response", False),
            privacy_mode=data.get("privacy_mode", False),
            custom_commands=data.get("custom_commands", {}),
        )


@dataclass(slots=True)
class UserProfile:
    """User profile"""
    username: str
    preferences: UserPreferences = field(default_factory=UserPreferences)
    created_at: float = 0.0
    last_active: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "username": self.username,
            "preferences": self.preferences.to_dict(),
            "created_at": self.created_at,
            "last_active": self.last_active,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        """Create from dictionary"""
        return cls(
            username=data["username"],
            preferences=UserPreferences.from_dict(data.get("preferences", {})),
            created_at=data.get("created_at", 0.0),
            last_active=data.get("last_active", 0.0),
        )


class PreferencesManager:
    """Manager for user preferences and profiles"""
    
    def __init__(self, config_file: Optional[Path] = None) -> None:
        """
        Initialize preferences manager
        
        Args:
            config_file: Path to preferences config file
        """
        self.config_file = config_file or Path.home() / ".nexora" / "preferences.json"
        self.profiles: dict[str, UserProfile] = {}
        self.current_user: Optional[str] = None
        self._load_preferences()
    
    def _load_preferences(self) -> None:
        """Load preferences from config file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    profiles_data = data.get("profiles", {})
                    for username, profile_data in profiles_data.items():
                        self.profiles[username] = UserProfile.from_dict(profile_data)
                    self.current_user = data.get("current_user")
            except Exception:
                self.profiles = {}
                self.current_user = None
        
        # Create default user if none exists
        if not self.profiles:
            self.create_profile("default")
            self.current_user = "default"
    
    def _save_preferences(self) -> None:
        """Save preferences to config file"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "current_user": self.current_user,
            "profiles": {username: profile.to_dict() for username, profile in self.profiles.items()}
        }
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def create_profile(self, username: str) -> UserProfile:
        """
        Create a new user profile
        
        Args:
            username: Username for the profile
            
        Returns:
            Created profile
        """
        import time
        profile = UserProfile(
            username=username,
            preferences=UserPreferences(),
            created_at=time.time(),
            last_active=time.time()
        )
        self.profiles[username] = profile
        self._save_preferences()
        return profile
    
    def get_profile(self, username: str) -> Optional[UserProfile]:
        """
        Get a user profile
        
        Args:
            username: Username
            
        Returns:
            Profile if exists, None otherwise
        """
        return self.profiles.get(username)
    
    def update_profile(self, username: str, preferences: UserPreferences) -> bool:
        """
        Update user preferences
        
        Args:
            username: Username
            preferences: New preferences
            
        Returns:
            True if updated, False otherwise
        """
        if username not in self.profiles:
            return False
        
        import time
        self.profiles[username].preferences = preferences
        self.profiles[username].last_active = time.time()
        self._save_preferences()
        return True
    
    def delete_profile(self, username: str) -> bool:
        """
        Delete a user profile
        
        Args:
            username: Username to delete
            
        Returns:
            True if deleted, False otherwise
        """
        if username not in self.profiles:
            return False
        
        del self.profiles[username]
        
        # Switch to default if current user was deleted
        if self.current_user == username:
            self.current_user = "default" if "default" in self.profiles else (list(self.profiles.keys())[0] if self.profiles else None)
        
        self._save_preferences()
        return True
    
    def set_current_user(self, username: str) -> bool:
        """
        Set the current active user
        
        Args:
            username: Username
            
        Returns:
            True if set, False otherwise
        """
        if username not in self.profiles:
            return False
        
        self.current_user = username
        self._save_preferences()
        return True
    
    def get_current_user(self) -> Optional[UserProfile]:
        """Get the current user's profile"""
        if self.current_user and self.current_user in self.profiles:
            return self.profiles[self.current_user]
        return None
    
    def get_preferences(self) -> Optional[UserPreferences]:
        """Get current user's preferences"""
        profile = self.get_current_user()
        return profile.preferences if profile else None
    
    def update_preference(self, key: str, value: Any) -> bool:
        """
        Update a single preference for current user
        
        Args:
            key: Preference key
            value: New value
            
        Returns:
            True if updated, False otherwise
        """
        profile = self.get_current_user()
        if not profile:
            return False
        
        if hasattr(profile.preferences, key):
            setattr(profile.preferences, key, value)
            import time
            profile.last_active = time.time()
            self._save_preferences()
            return True
        return False
    
    def list_profiles(self) -> list[dict[str, Any]]:
        """List all user profiles"""
        return [profile.to_dict() for profile in self.profiles.values()]


# Global preferences manager instance
global_preferences_manager = PreferencesManager()


def get_preferences() -> Optional[UserPreferences]:
    """Get current user's preferences from global manager"""
    return global_preferences_manager.get_preferences()


def update_preference(key: str, value: Any) -> bool:
    """Update a preference using the global manager"""
    return global_preferences_manager.update_preference(key, value)


def create_profile(username: str) -> UserProfile:
    """Create a profile using the global manager"""
    return global_preferences_manager.create_profile(username)


def set_current_user(username: str) -> bool:
    """Set current user using the global manager"""
    return global_preferences_manager.set_current_user(username)
