"""
Command Aliases Module
Allows users to create custom command shortcuts and aliases
"""
import json
from pathlib import Path
from typing import Any, Optional


class AliasManager:
    """Manager for command aliases"""
    
    def __init__(self, config_file: Optional[Path] = None) -> None:
        """
        Initialize alias manager
        
        Args:
            config_file: Path to aliases config file
        """
        self.config_file = config_file or Path.home() / ".nexora" / "aliases.json"
        self.aliases: dict[str, str] = {}
        self._load_aliases()
    
    def _load_aliases(self) -> None:
        """Load aliases from config file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    self.aliases = data.get("aliases", {})
            except Exception:
                self.aliases = {}
    
    def _save_aliases(self) -> None:
        """Save aliases to config file"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump({"aliases": self.aliases}, f, indent=2)
    
    def add_alias(self, alias: str, command: str) -> bool:
        """
        Add a new alias
        
        Args:
            alias: Shortcut name
            command: Full command to execute
            
        Returns:
            True if alias was added, False otherwise
        """
        if not alias or not command:
            return False
        
        self.aliases[alias.lower().strip()] = command.strip()
        self._save_aliases()
        return True
    
    def remove_alias(self, alias: str) -> bool:
        """
        Remove an alias
        
        Args:
            alias: Alias to remove
            
        Returns:
            True if alias was removed, False otherwise
        """
        alias_key = alias.lower().strip()
        if alias_key in self.aliases:
            del self.aliases[alias_key]
            self._save_aliases()
            return True
        return False
    
    def get_alias(self, alias: str) -> Optional[str]:
        """
        Get command for an alias
        
        Args:
            alias: Alias to look up
            
        Returns:
            Command if alias exists, None otherwise
        """
        return self.aliases.get(alias.lower().strip())
    
    def expand_command(self, command: str) -> str:
        """
        Expand command by replacing aliases
        
        Args:
            command: Command to expand
            
        Returns:
            Expanded command
        """
        words = command.split()
        if not words:
            return command
        
        first_word = words[0].lower()
        if first_word in self.aliases:
            # Replace alias with full command
            full_alias = self.aliases[first_word]
            # Append remaining words if any
            if len(words) > 1:
                return f"{full_alias} {' '.join(words[1:])}"
            return full_alias
        
        return command
    
    def list_aliases(self) -> list[dict[str, str]]:
        """List all aliases"""
        return [{"alias": alias, "command": command} for alias, command in self.aliases.items()]
    
    def import_aliases(self, aliases: dict[str, str]) -> int:
        """
        Import multiple aliases
        
        Args:
            aliases: Dictionary of aliases to import
            
        Returns:
            Number of aliases imported
        """
        count = 0
        for alias, command in aliases.items():
            if self.add_alias(alias, command):
                count += 1
        return count
    
    def export_aliases(self) -> dict[str, str]:
        """Export all aliases"""
        return dict(self.aliases)
    
    def clear_aliases(self) -> None:
        """Clear all aliases"""
        self.aliases.clear()
        self._save_aliases()


# Global alias manager instance
global_alias_manager = AliasManager()


def add_alias(alias: str, command: str) -> bool:
    """Add an alias to the global manager"""
    return global_alias_manager.add_alias(alias, command)


def remove_alias(alias: str) -> bool:
    """Remove an alias from the global manager"""
    return global_alias_manager.remove_alias(alias)


def expand_command(command: str) -> str:
    """Expand a command using the global manager"""
    return global_alias_manager.expand_command(command)


def list_aliases() -> list[dict[str, str]]:
    """List all aliases from the global manager"""
    return global_alias_manager.list_aliases()
