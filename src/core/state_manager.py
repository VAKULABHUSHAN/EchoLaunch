import enum
import threading
import time
from typing import Callable, List, Optional
from src.utils.logger import setup_logger

logger = setup_logger("StateManager")

class AssistantState(enum.Enum):
    STARTING = "STARTING"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    EXECUTING = "EXECUTING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"

class StateManager:
    """
    Thread-safe global state manager for the CLAPOS assistant.
    Tracks state transitions, speaking status, and self-listening guards.
    """
    def __init__(self, initial_state: AssistantState = AssistantState.STARTING, debug: bool = False):
        self._state = initial_state
        self._lock = threading.Lock()
        self.debug = debug
        self._listeners: List[Callable[[AssistantState, AssistantState], None]] = []

        # Self-listening flags
        self.is_speaking = False
        self.command_acceptance_paused = False
        self.last_speech_end_time = 0.0

    def add_listener(self, listener: Callable[[AssistantState, AssistantState], None]):
        """Registers a callback for state changes: callback(old_state, new_state)."""
        with self._lock:
            self._listeners.append(listener)

    def transition_to(self, new_state: AssistantState):
        """Transitions the assistant to a new state and notifies listeners."""
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return
            self._state = new_state
            if self.debug:
                logger.debug(f"[STATE] {new_state.value}")

        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state listener: {e}")

    @property
    def current_state(self) -> AssistantState:
        with self._lock:
            return self._state

    def set_speaking(self, speaking: bool):
        with self._lock:
            self.is_speaking = speaking
            if not speaking:
                self.last_speech_end_time = time.time()

    def set_command_acceptance_paused(self, paused: bool):
        with self._lock:
            self.command_acceptance_paused = paused
