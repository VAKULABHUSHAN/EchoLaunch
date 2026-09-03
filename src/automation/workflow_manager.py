import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from src.automation.app_launcher import AppLauncher
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logger

logger = setup_logger("WorkflowManager")

@dataclass
class WorkflowResult:
    workflow: str
    successful_apps: List[str] = field(default_factory=list)
    failed_apps: List[str] = field(default_factory=list)
    already_running_apps: List[str] = field(default_factory=list)

class WorkflowManager:
    """
    Manages desktop workflow executions.
    - Executes application launching asynchronously via a bounded worker queue.
    - Returns structured WorkflowResult details.
    - Never blocks voice listening or TTS threads.
    """
    def __init__(
        self,
        config_manager: ConfigManager,
        queue_size: int = 10,
        debug: bool = False
    ):
        self.config = config_manager
        self.debug = debug
        self.verification_timeout = float(self.config.get("workflow", "launch_verification_timeout", 5.0))

        self._queue = queue.Queue(maxsize=queue_size)
        self._is_running = False
        self._worker_thread: Optional[threading.Thread] = None

        self.on_workflow_complete: Optional[Callable[[WorkflowResult], None]] = None

    def set_callback(self, callback: Callable[[WorkflowResult], None]):
        self.on_workflow_complete = callback

    def start(self):
        """Starts the workflow background worker."""
        if self._is_running:
            return
        self._is_running = True
        self._worker_thread = threading.Thread(target=self._workflow_worker, daemon=False, name="WorkflowWorker")
        self._worker_thread.start()

    def trigger_workflow(self, workflow_key: str):
        """
        Enqueues a workflow for asynchronous execution. Non-blocking.
        """
        if not self._is_running:
            return

        try:
            self._queue.put_nowait(workflow_key)
        except queue.Full:
            logger.warning(f"[QUEUE] Workflow queue full — dropping workflow '{workflow_key}'")

    def _execute_workflow(self, workflow_key: str) -> WorkflowResult:
        workflows = self.config.get_section("workflows", {})
        wf_data = workflows.get(workflow_key)

        if not wf_data:
            logger.warning(f"Workflow '{workflow_key}' not found in configuration.")
            return WorkflowResult(workflow=workflow_key, failed_apps=[workflow_key])

        wf_name = wf_data.get("name", workflow_key)
        apps = wf_data.get("apps", [])

        if self.debug:
            logger.debug(f"[WORKFLOW] Launching {wf_name} ({len(apps)} apps)")

        result = WorkflowResult(workflow=wf_name)

        for app in apps:
            app_name = app.get("name", "Unknown App")
            app_path = app.get("path", "")
            app_args = app.get("arguments", "")

            success, status = AppLauncher.launch(app_name, app_path, arguments=app_args)

            if success:
                if status == "Already running":
                    result.already_running_apps.append(app_name)
                else:
                    result.successful_apps.append(app_name)
            else:
                result.failed_apps.append(app_name)

        return result

    def _workflow_worker(self):
        """Dedicated worker thread loop for launching workflows sequentially."""
        logger.info("Workflow worker loop active.")
        while self._is_running:
            try:
                workflow_key = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if workflow_key is None:
                self._queue.task_done()
                break

            try:
                result = self._execute_workflow(workflow_key)

                if self.on_workflow_complete:
                    try:
                        self.on_workflow_complete(result)
                    except Exception as e:
                        logger.error(f"Error in on_workflow_complete callback: {e}")

            except Exception as e:
                logger.error(f"Error executing workflow '{workflow_key}': {e}")
            finally:
                self._queue.task_done()

        logger.info("Workflow worker stopped.")

    def stop(self):
        """Stops the workflow worker cleanly."""
        self._is_running = False
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
