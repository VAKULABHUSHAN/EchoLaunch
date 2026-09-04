import json
import os
from typing import Dict, List, Set, Any, Optional
from src.utils.logger import setup_logger

logger = setup_logger("IntentDataset")

# Fallback default dataset if config/intent_keywords.json is missing
DEFAULT_INTENT_DATA = {
    "action_verbs": [
        "open", "launch", "start", "switch to", "activate", "turn on",
        "bring up", "run", "prepare", "set up", "setup", "boot", "load",
        "go to", "initiate", "lets", "let's"
    ],
    "mode_triggers": [
        "dev mode", "developer mode", "coding mode", "work mode",
        "gaming mode", "game mode", "entertainment mode", "chill mode", "youtube mode"
    ],
    "action_intents": {
        "DEVELOPER_MODE": {
            "targets": [
                "vscode", "vs code", "code", "coding", "dev mode", "developer mode",
                "coding mode", "work mode", "dev setup", "developer setup",
                "development setup", "coding setup", "development environment",
                "coding workspace", "workspace"
            ],
            "exact_phrases": [
                "dev mode", "developer mode", "coding mode", "work mode",
                "open vscode", "open vs code", "launch vscode", "launch vs code",
                "open code", "start coding", "start code", "let's code", "lets code", "let us code",
                "open my development setup", "open development setup",
                "open coding setup", "open dev setup", "open developer setup",
                "launch dev mode", "launch developer mode", "switch to dev mode",
                "switch to developer mode", "activate dev mode", "activate developer mode",
                "prepare my workspace", "prepare workspace", "prepare coding setup",
                "prepare dev setup", "prepare developer setup", "set up workspace",
                "setup workspace", "bring up vscode", "bring up code"
            ],
            "negative_exclusions": [
                "demo", "do more", "demonstration", "demonstrate"
            ]
        },
        "GAMING_MODE": {
            "targets": [
                "valorant", "game mode", "gaming mode", "gaming setup", "game setup", "games"
            ],
            "exact_phrases": [
                "game mode", "gaming mode", "open game mode", "open gaming mode",
                "launch valorant", "open valorant", "start valorant", "run valorant",
                "boot valorant", "play valorant", "start gaming", "start game",
                "let's play", "lets play", "let us play", "let's game", "lets game", "let us game",
                "open my games", "open games", "launch game mode", "launch gaming mode",
                "switch to game mode", "switch to gaming mode", "activate game mode",
                "activate gaming mode", "prepare gaming setup", "prepare game setup",
                "open gaming setup"
            ],
            "negative_exclusions": [
                "board game", "card game", "game over"
            ]
        },
        "ENTERTAINMENT_MODE": {
            "targets": [
                "youtube", "youtube mode", "entertainment mode", "chill mode"
            ],
            "exact_phrases": [
                "entertainment mode", "entertain mode", "youtube mode", "chill mode",
                "open youtube", "launch youtube", "start youtube", "play youtube",
                "watch youtube", "open youtube in chrome", "open video in youtube",
                "switch to entertainment mode", "activate entertainment mode",
                "launch entertainment mode"
            ],
            "negative_exclusions": []
        }
    },
    "conversational_intents": {
        "GREETING": {
            "exact_phrases": [
                "hello", "hey", "hi", "hey clapos", "hello clapos", "hi clapos",
                "good morning", "good afternoon", "good evening", "whats up", "what's up"
            ],
            "anchors": ["hello", "hey", "hi", "morning", "afternoon", "evening"]
        },
        "STATUS": {
            "exact_phrases": [
                "what are you doing", "are you listening", "are you there",
                "can you hear me", "status", "system status", "status report", "how are you"
            ],
            "anchors": ["listening", "status", "doing"]
        },
        "TIME": {
            "exact_phrases": [
                "what time is it", "tell me the time", "current time",
                "what's the time now", "whats the time now", "can you tell me the time",
                "what is the time", "time now", "tell time"
            ],
            "anchors": ["time", "clock"]
        }
    }
}


class IntentDataset:
    """
    Manages structured intent keywords, opening action verbs, mode triggers,
    and exclusion datasets for clean intent parsing without conversational false-positives.
    """
    def __init__(self, dataset_path: str = "config/intent_keywords.json"):
        self.dataset_path = dataset_path
        self.data: Dict[str, Any] = self._load()

        self.action_verbs: List[str] = self.data.get("action_verbs", DEFAULT_INTENT_DATA["action_verbs"])
        self.mode_triggers: List[str] = self.data.get("mode_triggers", DEFAULT_INTENT_DATA["mode_triggers"])
        self.action_intents: Dict[str, Dict[str, Any]] = self.data.get("action_intents", DEFAULT_INTENT_DATA["action_intents"])
        self.conversational_intents: Dict[str, Dict[str, Any]] = self.data.get("conversational_intents", DEFAULT_INTENT_DATA["conversational_intents"])

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.dataset_path):
            try:
                with open(self.dataset_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded intent dataset from {self.dataset_path}")
                    return data
            except Exception as e:
                logger.error(f"Failed to load dataset from {self.dataset_path}: {e}. Using fallback defaults.")
        else:
            logger.warning(f"Dataset file {self.dataset_path} not found. Using fallback defaults.")
        return DEFAULT_INTENT_DATA

    def get_all_phrases(self) -> Dict[str, List[str]]:
        """Returns a mapping of intent names to their exact command phrases."""
        phrases: Dict[str, List[str]] = {}
        for intent, info in self.action_intents.items():
            phrases[intent] = list(info.get("exact_phrases", []))
        for intent, info in self.conversational_intents.items():
            phrases[intent] = list(info.get("exact_phrases", []))
        return phrases

    def get_action_intent_names(self) -> Set[str]:
        return set(self.action_intents.keys())

    def get_conversational_intent_names(self) -> Set[str]:
        return set(self.conversational_intents.keys())

    def get_action_targets(self, intent: str) -> List[str]:
        return self.action_intents.get(intent, {}).get("targets", [])

    def get_negative_exclusions(self, intent: str) -> List[str]:
        return self.action_intents.get(intent, {}).get("negative_exclusions", [])

    def get_conversational_anchors(self, intent: str) -> List[str]:
        return self.conversational_intents.get(intent, {}).get("anchors", [])
