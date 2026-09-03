import json
import os
import re
from typing import Dict, Any
from src.utils.config_validator import ConfigValidator
from src.utils.logger import setup_logger

logger = setup_logger("ConfigManager")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Lightweight fallback .env loader
    env_file = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()


class ConfigManager:
    """
    Manages reading, validating, and writing to the config.json file.
    Supports environment variable expansion (${VAR_NAME}) from .env.
    """
    def __init__(self, config_path: str = "config/config.json", validate: bool = True):
        self.config_path = config_path
        self._config = self.load_config(validate=validate)

    def _expand_env_vars(self, data: Any) -> Any:
        """Recursively expands ${VAR} and %VAR% environment variables."""
        if isinstance(data, dict):
            return {k: self._expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._expand_env_vars(item) for item in data]
        elif isinstance(data, str):
            expanded = os.path.expandvars(data)
            # Match ${VAR_NAME} format
            for match in re.findall(r"\$\{([A-Za-z0-9_]+)\}", expanded):
                val = os.getenv(match, "")
                expanded = expanded.replace(f"${{{match}}}", val)
            return expanded
        return data

    def load_config(self, validate: bool = True) -> Dict[str, Any]:
        """Loads, expands env vars, and validates configuration from JSON file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found at: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw_cfg = json.load(f)

        # Expand environment variables from .env
        cfg = self._expand_env_vars(raw_cfg)

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
