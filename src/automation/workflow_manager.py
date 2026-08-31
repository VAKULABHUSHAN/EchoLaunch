import threading
from src.automation.app_launcher import AppLauncher
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logger

logger = setup_logger("WorkflowManager")

class WorkflowManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        
    def _execute_workflow(self, apps: list):
        """Executes a list of apps in a separate thread so it doesn't block audio."""
        for app in apps:
            name = app.get("name", "Unknown App")
            path = app.get("path", "")
            AppLauncher.launch(name, path)

    def trigger(self, clap_count: int):
        """Triggers the workflow associated with the given clap count."""
        commands = self.config.get("commands", str(clap_count))
        
        if not commands:
            logger.info(f"[ACTION] No action configured for {clap_count} claps")
            return
            
        workflow_name = commands.get("name", f"Workflow {clap_count}")
        apps = commands.get("apps", [])
        
        logger.info(f"[ACTION] Workflow Activated: {workflow_name}")
        
        # Run launching in a daemon thread to prevent blocking the audio stream or main loop
        threading.Thread(target=self._execute_workflow, args=(apps,), daemon=True).start()
