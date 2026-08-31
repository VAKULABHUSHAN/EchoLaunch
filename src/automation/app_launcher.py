import os
import subprocess
import psutil
from typing import Optional
from src.utils.logger import setup_logger

logger = setup_logger("AppLauncher")

class AppLauncher:
    @staticmethod
    def is_app_running(executable_name: str) -> bool:
        """Checks if a process with the given name is currently running."""
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and executable_name.lower() in proc.info['name'].lower():
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        return False

    @staticmethod
    def launch(app_name: str, app_path: str) -> bool:
        """Launches an application if it is not already running."""
        if not app_path:
            logger.error(f"Cannot launch {app_name}: Path is empty in configuration.")
            return False

        # Extract executable name for checking (e.g., "Code.exe" from "C:\\...\\Code.exe")
        executable_name = os.path.basename(app_path)
        
        # Some paths might be simple commands like "chrome.exe"
        if not executable_name:
            executable_name = app_path

        if AppLauncher.is_app_running(executable_name):
            logger.info(f"{app_name} is already running. Skipping.")
            return True

        try:
            # os.startfile is Windows-specific and handles paths and URIs nicely
            if os.name == 'nt':
                os.startfile(app_path)
            else:
                # Fallback for simple commands in PATH or non-Windows
                subprocess.Popen(app_path, shell=True)
                
            logger.info(f"Launched: {app_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to launch {app_name} at {app_path}: {e}")
            return False
