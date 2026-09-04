import unittest
from src.core.intent_engine import IntentEngine


class TestIntentEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = IntentEngine(
            conversation_threshold=0.65,
            action_threshold=0.82,
            dataset_path="config/intent_keywords.json"
        )

    def test_developer_mode_positive_commands(self):
        commands = [
            "dev mode",
            "developer mode",
            "coding mode",
            "open vscode",
            "open vs code",
            "launch vscode",
            "start coding",
            "let's code",
            "lets code",
            "let us code",
            "open my development setup",
            "prepare workspace",
            "prepare my workspace",
            "hey clapos please open vscode",
            "can you activate developer mode",
            "switch to dev mode",
            "bring up vscode"
        ]
        for cmd in commands:
            with self.subTest(command=cmd):
                res = self.engine.parse_intent(cmd)
                self.assertEqual(
                    res.intent,
                    "DEVELOPER_MODE",
                    f"Expected DEVELOPER_MODE for '{cmd}', got {res.intent} (conf={res.confidence})"
                )
                self.assertGreaterEqual(res.confidence, 0.82)

    def test_gaming_mode_positive_commands(self):
        commands = [
            "game mode",
            "gaming mode",
            "launch valorant",
            "open valorant",
            "start valorant",
            "start gaming",
            "let's play",
            "lets play",
            "let us play",
            "let's game",
            "open my games",
            "can you launch valorant",
            "switch to game mode",
            "activate gaming mode",
            "prepare gaming setup"
        ]
        for cmd in commands:
            with self.subTest(command=cmd):
                res = self.engine.parse_intent(cmd)
                self.assertEqual(
                    res.intent,
                    "GAMING_MODE",
                    f"Expected GAMING_MODE for '{cmd}', got {res.intent} (conf={res.confidence})"
                )
                self.assertGreaterEqual(res.confidence, 0.82)

    def test_entertainment_mode_positive_commands(self):
        commands = [
            "entertainment mode",
            "youtube mode",
            "open youtube",
            "launch youtube",
            "watch youtube",
            "play youtube",
            "open youtube in chrome",
            "hey clapos please open youtube",
            "switch to entertainment mode"
        ]
        for cmd in commands:
            with self.subTest(command=cmd):
                res = self.engine.parse_intent(cmd)
                self.assertEqual(
                    res.intent,
                    "ENTERTAINMENT_MODE",
                    f"Expected ENTERTAINMENT_MODE for '{cmd}', got {res.intent} (conf={res.confidence})"
                )
                self.assertGreaterEqual(res.confidence, 0.82)

    def test_conversational_false_positives_rejected(self):
        """
        Verify that casual speech, discussions, and partial words DO NOT
        accidentally trigger desktop application launches.
        """
        casual_phrases = [
            "we need to do more testing before release",
            "do more work",
            "can you give me a demo",
            "show me the demo",
            "lets see a demo",
            "i am talking to the developer",
            "good work developer",
            "check out the dev branch",
            "are you playing a game",
            "that was an amazing game",
            "i like playing football",
            "we played a board game",
            "i watched a video today",
            "i really like youtube",
            "check out this youtube link",
            "i just want to relax and chill",
            "she gave a good demonstration",
            "we need more time for this feature",
            "can you explain this code to me"
        ]
        for phrase in casual_phrases:
            with self.subTest(phrase=phrase):
                res = self.engine.parse_intent(phrase)
                self.assertNotEqual(
                    res.intent,
                    "DEVELOPER_MODE",
                    f"False positive DEVELOPER_MODE on '{phrase}' (conf={res.confidence})"
                )
                self.assertNotEqual(
                    res.intent,
                    "GAMING_MODE",
                    f"False positive GAMING_MODE on '{phrase}' (conf={res.confidence})"
                )
                self.assertNotEqual(
                    res.intent,
                    "ENTERTAINMENT_MODE",
                    f"False positive ENTERTAINMENT_MODE on '{phrase}' (conf={res.confidence})"
                )

    def test_conversational_intents(self):
        greetings = ["hello", "hey", "hi", "hey clapos", "good morning", "good evening"]
        for g in greetings:
            with self.subTest(greeting=g):
                res = self.engine.parse_intent(g)
                self.assertEqual(res.intent, "GREETING")
                self.assertGreaterEqual(res.confidence, 0.65)

        time_queries = ["what time is it", "tell me the time", "current time", "can you tell me the time"]
        for t in time_queries:
            with self.subTest(time_query=t):
                res = self.engine.parse_intent(t)
                self.assertEqual(res.intent, "TIME")
                self.assertGreaterEqual(res.confidence, 0.65)

        status_queries = ["are you listening", "can you hear me", "system status", "status"]
        for s in status_queries:
            with self.subTest(status_query=s):
                res = self.engine.parse_intent(s)
                self.assertEqual(res.intent, "STATUS")
                self.assertGreaterEqual(res.confidence, 0.65)


if __name__ == "__main__":
    unittest.main()
