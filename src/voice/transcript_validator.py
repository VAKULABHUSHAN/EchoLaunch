import re
from typing import Tuple
from src.utils.logger import setup_logger

logger = setup_logger("TranscriptValidator")

class TranscriptValidator:
    """
    Validates Whisper transcripts to prevent hallucinations, noise captures,
    and phantom phrases from reaching the Intent Engine.
    """
    # Common Whisper hallucination strings caused by silence or background noise
    KNOWN_HALLUCINATIONS = {
        "[blank_audio]", "(bell rings)", "(silence)", "(music)",
        "thank you for watching", "thanks for watching", "subscribe",
        "please subscribe", "subtitles by", "amara.org",
        "you", "thank you", "thanks"
    }

    def __init__(
        self,
        min_log_probability: float = -1.0,
        max_no_speech_probability: float = 0.6,
        minimum_text_length: int = 2
    ):
        self.min_log_probability = min_log_probability
        self.max_no_speech_probability = max_no_speech_probability
        self.minimum_text_length = minimum_text_length

    def clean_text(self, text: str) -> str:
        """Removes punctuation and normalizes spacing and casing."""
        # Strip brackets/parentheses and their content if they look like tags
        text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
        # Remove punctuation
        text = re.sub(r"[^\w\s]", "", text)
        # Normalize whitespace
        text = " ".join(text.split()).strip().lower()
        return text

    def _is_repetitive_loop(self, words: list) -> bool:
        """Detects repetitive word hallucinations (e.g., 'word word word')."""
        if len(words) >= 4:
            # Check if all words are identical
            if len(set(words)) == 1:
                return True
            # Check if 2-gram repeats 3+ times
            if len(words) >= 6:
                half = len(words) // 2
                if words[:half] == words[half:2*half]:
                    return True
        return False

    def validate(
        self,
        raw_text: str,
        avg_logprob: float = 0.0,
        no_speech_prob: float = 0.0
    ) -> Tuple[bool, str, str]:
        """
        Validates raw transcription text against confidence thresholds and hallucination heuristics.
        Returns: (is_valid, cleaned_text, reason)
        """
        if not raw_text or not raw_text.strip():
            return False, "", "Empty transcript"

        cleaned = self.clean_text(raw_text)

        if len(cleaned) < self.minimum_text_length:
            return False, cleaned, f"Text length ({len(cleaned)}) below minimum ({self.minimum_text_length})"

        # Check no-speech probability
        if no_speech_prob > self.max_no_speech_probability:
            return False, cleaned, f"High no_speech_prob ({no_speech_prob:.2f} > {self.max_no_speech_probability:.2f})"

        # Check average log probability
        if avg_logprob < self.min_log_probability:
            return False, cleaned, f"Low avg_logprob ({avg_logprob:.2f} < {self.min_log_probability:.2f})"

        # Check known hallucination strings
        if cleaned in self.KNOWN_HALLUCINATIONS:
            return False, cleaned, "Matches known hallucination phrase"

        # Check repetitive words
        words = cleaned.split()
        if self._is_repetitive_loop(words):
            return False, cleaned, "Repetitive hallucination loop detected"

        return True, cleaned, "Valid"
