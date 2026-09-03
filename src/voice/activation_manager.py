import enum
from typing import Optional
from src.utils.logger import setup_logger

logger = setup_logger("ActivationManager")

class ActivationMode(enum.Enum):
    CONTINUOUS_COMMAND = "CONTINUOUS_COMMAND"
    WAKE_WORD = "WAKE_WORD"
    PUSH_TO_TALK = "PUSH_TO_TALK"

class ActivationManager:
    """
    Manages interaction modes and voice activation states.
    Supports:
    - CONTINUOUS_COMMAND: All detected speech segments are treated as commands (default for V3).
    - WAKE_WORD: Ready for future "Hey CLAPOS" wake word engine.
    - PUSH_TO_TALK: Only processes speech when activated via hotkey/button.
    """
    def __init__(self, mode: str = "CONTINUOUS_COMMAND"):
        try:
            self.mode = ActivationMode(mode)
        except ValueError:
            logger.warning(f"Unknown activation mode '{mode}', defaulting to CONTINUOUS_COMMAND.")
            self.mode = ActivationMode.CONTINUOUS_COMMAND
            
        self._is_active = (self.mode == ActivationMode.CONTINUOUS_COMMAND)

    def should_process_speech(self) -> bool:
        """Determines if the speech segment should proceed to transcript validation and intent parsing."""
        if self.mode == ActivationMode.CONTINUOUS_COMMAND:
            return True
        return self._is_active

    def on_wake_word(self):
        """Called when a wake word is detected."""
        if self.mode == ActivationMode.WAKE_WORD:
            self._is_active = True
            logger.info("[ACTIVATION] Wake word detected. Ready for command.")

    def set_push_to_talk(self, active: bool):
        """Sets push-to-talk state."""
        if self.mode == ActivationMode.PUSH_TO_TALK:
            self._is_active = active

    def reset_after_command(self):
        """Resets active state after a command has been handled (for WAKE_WORD and PUSH_TO_TALK)."""
        if self.mode != ActivationMode.CONTINUOUS_COMMAND:
            self._is_active = False
