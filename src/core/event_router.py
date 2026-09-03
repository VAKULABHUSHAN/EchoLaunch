import random
import time
from typing import Dict, List, Optional
from src.core.intent_engine import IntentResult
from src.core.command_history import CommandHistory
from src.voice.tts_engine import TTSEngine
from src.automation.workflow_manager import WorkflowManager, WorkflowResult
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logger

logger = setup_logger("EventRouter")

class EventRouter:
    """
    Decoupled Event Router:
    - Enforces global cooldown, duplicate intent window, and unknown command cooldown.
    - Decouples verbal responses (sent to TTSEngine) from workflow execution (sent to WorkflowManager).
    - Checks automation.enabled configuration for safe testing without application launches.
    - Generates dynamic natural responses (e.g., local system time).
    - Handles workflow completion and failure feedback.
    """
    def __init__(
        self,
        config_manager: ConfigManager,
        tts_engine: TTSEngine,
        workflow_manager: WorkflowManager,
        command_history: CommandHistory,
        debug: bool = False
    ):
        self.config = config_manager
        self.tts = tts_engine
        self.workflow_manager = workflow_manager
        self.command_history = command_history
        self.debug = debug

        # Timing and cooldown settings
        intent_cfg = self.config.get_section("intent", {})
        self.global_cooldown = float(intent_cfg.get("global_cooldown", 2.0))
        self.duplicate_intent_window = float(intent_cfg.get("duplicate_intent_window", 5.0))
        self.unknown_command_cooldown = float(intent_cfg.get("unknown_command_cooldown", 4.0))

        # Cooldown state tracking
        self.last_command_time = 0.0
        self.last_intent = ""
        self.last_intent_time = 0.0
        self.last_unknown_time = 0.0

        # Hook workflow completion callback
        self.workflow_manager.set_callback(self._on_workflow_completed)

    def route_intent(
        self,
        intent_res: IntentResult,
        stt_latency_ms: float = 0.0,
        intent_latency_ms: float = 0.0
    ) -> float:
        """
        Routes the recognized intent to verbal response and desktop automation.
        Returns the response queue latency in milliseconds.
        """
        now = time.time()
        intent = intent_res.intent
        confidence = intent_res.confidence
        raw_text = intent_res.original_text

        # -------------------------------------------------------------
        # 1. Cooldown & Duplicate Checks
        # -------------------------------------------------------------
        if intent == "UNKNOWN":
            if now - self.last_unknown_time < self.unknown_command_cooldown:
                if self.debug:
                    print(f"[COOLDOWN] Suppressing repeated unknown command ({now - self.last_unknown_time:.1f}s < {self.unknown_command_cooldown}s)")
                return 0.0
            self.last_unknown_time = now
        else:
            # Check global command cooldown
            if now - self.last_command_time < self.global_cooldown:
                if self.debug:
                    print(f"[COOLDOWN] Ignored command within global cooldown ({now - self.last_command_time:.1f}s < {self.global_cooldown}s)")
                return 0.0

            # Check duplicate intent window
            if intent == self.last_intent and (now - self.last_intent_time < self.duplicate_intent_window):
                if self.debug:
                    print(f"[COOLDOWN] Ignored duplicate intent '{intent}' within window ({now - self.last_intent_time:.1f}s < {self.duplicate_intent_window}s)")
                return 0.0

            self.last_command_time = now
            self.last_intent = intent
            self.last_intent_time = now

        # -------------------------------------------------------------
        # 2. Generate Verbal Response
        # -------------------------------------------------------------
        response_text = self._generate_response(intent)
        t_queue_start = time.time()

        if response_text:
            print(f"\n[RESPONSE] {response_text}")
            self.tts.speak(response_text)

        response_queue_latency_ms = (time.time() - t_queue_start) * 1000
        total_latency_ms = stt_latency_ms + intent_latency_ms + response_queue_latency_ms

        # -------------------------------------------------------------
        # 3. Route Workflows (with automation.enabled check)
        # -------------------------------------------------------------
        automation_enabled = self.config.get("automation", "enabled", False)

        if intent == "DEVELOPER_MODE":
            if not automation_enabled:
                print("\n[WORKFLOW] Developer Mode detected\n[WORKFLOW] Automation disabled (debug mode)")
            else:
                self.workflow_manager.trigger_workflow("dev_mode")
        elif intent == "GAMING_MODE":
            if not automation_enabled:
                print("\n[WORKFLOW] Gaming Mode detected\n[WORKFLOW] Automation disabled (debug mode)")
            else:
                self.workflow_manager.trigger_workflow("game_mode")

        # -------------------------------------------------------------
        # 4. Record to Command History
        # -------------------------------------------------------------
        status = "EXECUTED" if (intent != "UNKNOWN" and automation_enabled) else ("SIMULATED" if not automation_enabled else "UNKNOWN")
        self.command_history.record(
            transcript=raw_text,
            intent=intent,
            confidence=confidence,
            execution_status=status,
            stt_latency_ms=stt_latency_ms,
            intent_latency_ms=intent_latency_ms,
            total_latency_ms=total_latency_ms
        )

        return response_queue_latency_ms

    def _generate_response(self, intent: str) -> Optional[str]:
        """Generates natural varied assistant responses."""
        responses_dict = self.config.get_section("responses", {})

        if intent == "TIME":
            # Natural 12-hour format e.g. "7:30 PM"
            now = time.localtime()
            formatted_time = time.strftime("%I:%M %p", now).lstrip("0")
            return f"The time is {formatted_time}."

        options = responses_dict.get(intent)
        if options and isinstance(options, list):
            return random.choice(options)

        if intent == "UNKNOWN":
            return "I didn't quite understand that."

        return None

    def _on_workflow_completed(self, result: WorkflowResult):
        """Handles post-workflow completion or failure voice notifications."""
        if result.failed_apps:
            failed_names = ", ".join(result.failed_apps)
            error_msg = f"I couldn't open {failed_names}. Please check the application path."
            logger.warning(f"[WORKFLOW ERROR] {error_msg}")
            print(f"\n[RESPONSE] {error_msg}\n")
            self.tts.speak(error_msg)
            return

        # Speak after opening applications
        completion_feedback = self.config.get("assistant", "completion_feedback", True)
        if completion_feedback:
            if "Developer" in result.workflow:
                msg = "Your development environment is ready."
            elif "Gaming" in result.workflow:
                msg = "Your gaming environment is ready."
            else:
                msg = f"Your {result.workflow} is ready."

            print(f"\n[RESPONSE] {msg}\n")
            self.tts.speak(msg)
