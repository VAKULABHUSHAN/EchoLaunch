import json
import os
from pathlib import Path
from typing import Dict, Any

class ConfigManager:
    """Manages reading and writing to the config.json file."""
    
    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = config_path
        self._config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Loads configuration from JSON file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found at: {self.config_path}")
            
        with open(self.config_path, 'r') as f:
            return json.load(f)
            
    def save_config(self):
        """Saves current configuration state back to the JSON file."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=4)
            
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Retrieves a configuration value."""
        return self._config.get(section, {}).get(key, default)
        
    def set(self, section: str, key: str, value: Any):
        """Sets a configuration value and saves the config."""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
        self.save_config()

    @property
    def config(self) -> Dict[str, Any]:
        """Returns the full configuration dictionary."""
        return self._config
