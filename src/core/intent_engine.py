import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from rapidfuzz import fuzz
from src.utils.logger import setup_logger

logger = setup_logger("IntentEngine")

@dataclass
class IntentResult:
    intent: str
    confidence: float
    original_text: str

class IntentEngine:
    """
    3-Layer Intent Understanding Engine:
    - Layer 1: Exact normalized phrase matching
    - Layer 2: Semantic / Key phrase matching with required semantic anchors
    - Layer 3: Fuzzy matching (Rapidfuzz) with anchor verification

    Supports common Whisper phonetic transcriptions of short spoken words
    like 'dev mode' ('demo', 'do more', 'deve mode', 'deb mode').
    """
    CONVERSATIONAL_INTENTS = {"GREETING", "STATUS", "TIME"}
    ACTION_INTENTS = {"DEVELOPER_MODE", "GAMING_MODE"}

    # Comprehensive dictionaries of natural intent phrases
    INTENT_PHRASES: Dict[str, List[str]] = {
        "DEVELOPER_MODE": [
            "dev mode", "developer mode", "coding mode", "work mode",
            "open my development setup", "open development setup",
            "start coding", "open vscode", "open code", "let's code", "lets code",
            "prepare my workspace", "prepare coding setup", "prepare workspace",
            "coding setup", "dev setup", "developer setup", "code mode",
            # Common acoustic/phonetic transcriptions of short "dev mode"
            "demo", "do more", "deb mode", "def mode", "deve mode", "dev", "developer"
        ],
        "GAMING_MODE": [
            "game mode", "gaming mode", "play mode", "let's play", "lets play",
            "start gaming", "launch valorant", "open valorant", "prepare gaming setup",
            "open my games", "open games", "gaming setup", "game setup", "game", "gaming"
        ],
        "GREETING": [
            "hello", "hey", "hi", "hey clapos", "hello clapos", "hi clapos",
            "good morning", "good afternoon", "good evening", "whats up", "what's up"
        ],
        "STATUS": [
            "what are you doing", "are you listening", "are you there",
            "can you hear me", "status", "system status", "how are you"
        ],
        "TIME": [
            "what time is it", "tell me the time", "current time",
            "what's the time now", "whats the time now", "can you tell me the time",
            "what is the time", "time now", "tell time"
        ]
    }

    # Semantic anchor keywords required for each intent category
    SEMANTIC_ANCHORS: Dict[str, Set[str]] = {
        "DEVELOPER_MODE": {"dev", "developer", "coding", "vscode", "code", "workspace", "demo", "deve", "more"},
        "GAMING_MODE": {"game", "gaming", "valorant", "games", "play"},
        "GREETING": {"hello", "hey", "hi", "morning", "afternoon", "evening"},
        "STATUS": {"doing", "listening", "status"},
        "TIME": {"time", "clock"}
    }

    def __init__(
        self,
        conversation_threshold: float = 0.65,
        action_threshold: float = 0.82
    ):
        self.conversation_threshold = conversation_threshold
        self.action_threshold = action_threshold

    def _normalize(self, text: str) -> str:
        """Lowercases, removes punctuation, and normalizes whitespace."""
        text = re.sub(r"[^\w\s]", "", text)
        return " ".join(text.split()).strip().lower()

    def parse_intent(self, raw_text: str) -> IntentResult:
        """
        Parses text through Layer 1 (Exact), Layer 2 (Semantic), and Layer 3 (Fuzzy).
        Applies tiered confirmation thresholds.
        """
        normalized = self._normalize(raw_text)
        if not normalized:
            return IntentResult("UNKNOWN", 0.0, raw_text)

        words = set(normalized.split())

        # -------------------------------------------------------------
        # LAYER 1: Exact Phrase Matching
        # -------------------------------------------------------------
        for intent, phrases in self.INTENT_PHRASES.items():
            for phrase in phrases:
                if normalized == self._normalize(phrase):
                    return IntentResult(intent, 1.0, raw_text)

        # -------------------------------------------------------------
        # LAYER 2: Semantic / Substring Matching
        # -------------------------------------------------------------
        for intent, phrases in self.INTENT_PHRASES.items():
            anchors = self.SEMANTIC_ANCHORS.get(intent, set())
            # Require at least one anchor word to be present
            if not words.intersection(anchors):
                continue

            for phrase in phrases:
                clean_phrase = self._normalize(phrase)
                # Check if multi-word phrase is contained in input
                if clean_phrase in normalized:
                    conf = 0.95
                    if self._check_threshold(intent, conf):
                        return IntentResult(intent, conf, raw_text)

        # -------------------------------------------------------------
        # LAYER 3: Fuzzy Matching Fallback (with semantic anchor validation)
        # -------------------------------------------------------------
        best_intent = "UNKNOWN"
        highest_score = 0.0

        for intent, phrases in self.INTENT_PHRASES.items():
            anchors = self.SEMANTIC_ANCHORS.get(intent, set())
            # Must contain a semantic anchor for this intent
            if not words.intersection(anchors):
                continue

            for phrase in phrases:
                clean_phrase = self._normalize(phrase)
                score_sort = fuzz.token_sort_ratio(normalized, clean_phrase)
                score_ratio = fuzz.ratio(normalized, clean_phrase)
                score = (score_sort * 0.7 + score_ratio * 0.3) / 100.0

                if score > highest_score:
                    highest_score = score
                    best_intent = intent

        if self._check_threshold(best_intent, highest_score):
            return IntentResult(best_intent, round(highest_score, 2), raw_text)

        return IntentResult("UNKNOWN", round(highest_score, 2), raw_text)

    def _check_threshold(self, intent: str, confidence: float) -> bool:
        """Validates score against tiered confidence thresholds."""
        if intent in self.ACTION_INTENTS:
            return confidence >= self.action_threshold
        elif intent in self.CONVERSATIONAL_INTENTS:
            return confidence >= self.conversation_threshold
        return False
