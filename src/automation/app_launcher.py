import os
import subprocess
import time
import psutil
from typing import Optional, Tuple
from src.utils.logger import setup_logger

logger = setup_logger("AppLauncher")

class AppLauncher:
    """
    Handles process detection and application launching on Windows.
    Uses native Windows shell execution (os.startfile) with support for shortcuts (.lnk) and arguments.
    """
    @staticmethod
    def is_app_running(target_name: str) -> bool:
        """
        Checks if a process matching target_name is currently running.
        target_name can be an executable name ('Code.exe'), shortcut name ('VALORANT.lnk'), or app name.
        """
        target = target_name.lower().replace(".exe", "").replace(".lnk", "")
        try:
            for proc in psutil.process_iter(['name']):
                p_name = proc.info.get('name')
                if p_name and target in p_name.lower():
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        return False

    @staticmethod
    def launch(app_name: str, app_path: str, arguments: str = "") -> Tuple[bool, str]:
        """
        Launches an application if it is not already running.
        Special handling for games like VALORANT that require Riot Client / shortcuts.
        """
        if not app_path or not app_path.strip():
            logger.error(f"Cannot launch '{app_name}': Path is empty.")
            return False, "Empty path"

        # Special automatic resolution for VALORANT to prevent [WinError 5] Access Denied
        if "valorant" in app_name.lower() or "valorant.exe" in app_path.lower():
            # Check for Desktop shortcut first
            user_desktop = os.path.expanduser(r"~\Desktop\VALORANT.lnk")
            if os.path.exists(user_desktop):
                app_path = user_desktop
                arguments = ""
            elif os.path.exists(r"C:\Users\VAKUL\Desktop\VALORANT.lnk"):
                app_path = r"C:\Users\VAKUL\Desktop\VALORANT.lnk"
                arguments = ""
            elif os.path.exists(r"C:\Riot Games\Riot Client\RiotClientServices.exe"):
                app_path = r"C:\Riot Games\Riot Client\RiotClientServices.exe"
                arguments = "--launch-product=valorant --launch-patchline=live"

        # Determine process name to check
        exe_name = os.path.basename(app_path)
        if not exe_name or ":" in exe_name or exe_name.lower().endswith(".lnk"):
            exe_name = app_name

        # If already running and no specific arguments (e.g. URLs) are passed, skip duplicate launch
        if AppLauncher.is_app_running(exe_name) and not arguments:
            logger.info(f"'{app_name}' is already running.")
            return True, "Already running"

        try:
            if os.name == 'nt':
                if arguments:
                    os.startfile(app_path, "open", arguments)
                else:
                    os.startfile(app_path)
            else:
                cmd = f"{app_path} {arguments}".strip()
                subprocess.Popen(
                    cmd,
                    shell=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            logger.info(f"Launch command issued for '{app_name}'.")
            return True, "Launched"
        except Exception as e:
            logger.error(f"Failed to launch '{app_name}' at {app_path}: {e}")
            return False, str(e)

    @staticmethod
    def verify_running(app_name: str, app_path: str, timeout: float = 5.0) -> bool:
        """
        Polls for the application to appear in the process list up to timeout seconds.
        """
        exe_name = os.path.basename(app_path)
        if not exe_name or ":" in exe_name or exe_name.lower().endswith(".lnk"):
            exe_name = app_name

        start = time.time()
        while time.time() - start < timeout:
            if AppLauncher.is_app_running(exe_name):
                return True
            time.sleep(0.5)
        return False
