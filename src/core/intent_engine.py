import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from rapidfuzz import fuzz
from src.core.intent_dataset import IntentDataset
from src.utils.logger import setup_logger

logger = setup_logger("IntentEngine")

@dataclass
class IntentResult:
    intent: str
    confidence: float
    original_text: str

class IntentEngine:
    """
    3-Layer Intent Understanding Engine with Strict False-Positive Protection:
    - Layer 1: Exact normalized phrase matching against defined command phrases.
    - Layer 2: Semantic command structure matching:
        * Whole-word phrase boundary checking (\\b)
        * Mandatory [Action Verb] + [Target Entity] or [Mode Trigger] for action intents
        * Negative exclusion filtering to block conversational traps (e.g. "demo", "do more")
    - Layer 3: Rapidfuzz fallback with strict gating (action intents require action/mode keywords).
    """
    CONVERSATIONAL_INTENTS = {"GREETING", "STATUS", "TIME"}
    ACTION_INTENTS = {"DEVELOPER_MODE", "GAMING_MODE", "ENTERTAINMENT_MODE"}

    def __init__(
        self,
        conversation_threshold: float = 0.65,
        action_threshold: float = 0.82,
        dataset_path: str = "config/intent_keywords.json"
    ):
        self.conversation_threshold = conversation_threshold
        self.action_threshold = action_threshold
        self.dataset = IntentDataset(dataset_path=dataset_path)

        # Sync intent sets with dataset
        self.ACTION_INTENTS = self.dataset.get_action_intent_names() or self.ACTION_INTENTS
        self.CONVERSATIONAL_INTENTS = self.dataset.get_conversational_intent_names() or self.CONVERSATIONAL_INTENTS
        self.INTENT_PHRASES = self.dataset.get_all_phrases()

    def _normalize(self, text: str) -> str:
        """Lowercases, removes apostrophes, strips punctuation, and normalizes whitespace."""
        text = text.replace("'", "").replace("’", "")
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split()).strip().lower()

    def _has_action_verb(self, normalized: str) -> bool:
        """Checks if any defined action verb is present as a whole word."""
        for verb in self.dataset.action_verbs:
            clean_v = self._normalize(verb)
            if re.search(rf"\b{re.escape(clean_v)}\b", normalized):
                return True
        return False

    def _has_mode_trigger(self, normalized: str) -> bool:
        """Checks if any defined mode trigger is present as a whole phrase."""
        for mode in self.dataset.mode_triggers:
            clean_m = self._normalize(mode)
            if re.search(rf"\b{re.escape(clean_m)}\b", normalized):
                return True
        return False

    def _matches_negative_exclusions(self, intent: str, normalized: str) -> bool:
        """Returns True if the text contains any negative exclusion phrases for the intent."""
        exclusions = self.dataset.get_negative_exclusions(intent)
        for excl in exclusions:
            clean_excl = self._normalize(excl)
            if re.search(rf"\b{re.escape(clean_excl)}\b", normalized):
                return True
        return False

    def parse_intent(self, raw_text: str) -> IntentResult:
        """
        Parses text through Layer 1 (Exact), Layer 2 (Semantic/Trigger), and Layer 3 (Fuzzy).
        Applies strict gating to prevent casual conversation from triggering desktop actions.
        """
        normalized = self._normalize(raw_text)
        if not normalized:
            return IntentResult("UNKNOWN", 0.0, raw_text)

        words = set(normalized.split())

        # -------------------------------------------------------------
        # LAYER 1: Exact Full-Phrase Matching
        # -------------------------------------------------------------
        for intent, phrases in self.INTENT_PHRASES.items():
            for phrase in phrases:
                if normalized == self._normalize(phrase):
                    return IntentResult(intent, 1.0, raw_text)

        has_action_verb = self._has_action_verb(normalized)
        has_mode_trigger = self._has_mode_trigger(normalized)

        # -------------------------------------------------------------
        # LAYER 2: Semantic / Action Command Structure Matching
        # -------------------------------------------------------------
        # 2A. Action Intents: Must have explicit command structure
        for intent in self.ACTION_INTENTS:
            # Check negative exclusion phrases first
            if self._matches_negative_exclusions(intent, normalized):
                continue

            # Check if any multi-word exact phrase is embedded with word boundaries
            phrases = self.INTENT_PHRASES.get(intent, [])
            matched_phrase = False
            for phrase in phrases:
                clean_phrase = self._normalize(phrase)
                # Only match multi-word phrases or mode triggers to avoid single-word accidents
                if " " in clean_phrase or clean_phrase in self.dataset.mode_triggers:
                    if re.search(rf"\b{re.escape(clean_phrase)}\b", normalized):
                        matched_phrase = True
                        break

            if matched_phrase:
                conf = 0.95
                if self._check_threshold(intent, conf):
                    return IntentResult(intent, conf, raw_text)

            # Check dynamic [Action Verb / Mode Trigger] + [Target Anchor]
            if has_action_verb or has_mode_trigger:
                targets = self.dataset.get_action_targets(intent)
                for target in targets:
                    clean_target = self._normalize(target)
                    if re.search(rf"\b{re.escape(clean_target)}\b", normalized):
                        conf = 0.95
                        if self._check_threshold(intent, conf):
                            return IntentResult(intent, conf, raw_text)

        # 2B. Conversational Intents: Match embedded conversational phrases with word boundaries
        for intent in self.CONVERSATIONAL_INTENTS:
            phrases = self.INTENT_PHRASES.get(intent, [])
            for phrase in phrases:
                clean_phrase = self._normalize(phrase)
                if re.search(rf"\b{re.escape(clean_phrase)}\b", normalized):
                    conf = 0.92
                    if self._check_threshold(intent, conf):
                        return IntentResult(intent, conf, raw_text)

        # -------------------------------------------------------------
        # LAYER 3: Fuzzy Matching Fallback (Strictly Gated)
        # -------------------------------------------------------------
        best_intent = "UNKNOWN"
        highest_score = 0.0

        for intent, phrases in self.INTENT_PHRASES.items():
            is_action = intent in self.ACTION_INTENTS

            # Strict guard: For action intents, DO NOT fuzzy match casual speech without action/mode triggers
            if is_action:
                if not (has_action_verb or has_mode_trigger):
                    continue
                if self._matches_negative_exclusions(intent, normalized):
                    continue

            # For conversational intents, require at least one conversational anchor word
            if not is_action:
                anchors = set(self.dataset.get_conversational_anchors(intent))
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
