import json
import os
from typing import Dict, Any
from src.utils.config_validator import ConfigValidator
from src.utils.logger import setup_logger

logger = setup_logger("ConfigManager")

class ConfigManager:
    """Manages reading, validating, and writing to the config.json file."""
    
    def __init__(self, config_path: str = "config/config.json", validate: bool = True):
        self.config_path = config_path
        self._config = self.load_config(validate=validate)
        
    def load_config(self, validate: bool = True) -> Dict[str, Any]:
        """Loads and validates configuration from JSON file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found at: {self.config_path}")
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)

        if validate:
            ConfigValidator.validate(cfg)
            
        return cfg
            
    def save_config(self):
        """Saves current configuration state back to the JSON file."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=4)
            
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Retrieves a configuration value."""
        sec = self._config.get(section, {})
        if isinstance(sec, dict):
            return sec.get(key, default)
        return default
        
    def get_section(self, section: str, default: Any = None) -> Any:
        """Retrieves an entire configuration section."""
        return self._config.get(section, default if default is not None else {})

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
