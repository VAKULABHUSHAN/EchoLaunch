import time
import collections
import threading
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CommandHistoryEntry:
    timestamp: float
    formatted_time: str
    transcript: str
    intent: str
    confidence: float
    execution_status: str
    stt_latency_ms: float = 0.0
    intent_latency_ms: float = 0.0
    total_latency_ms: float = 0.0

class CommandHistory:
    """
    Thread-safe circular in-memory buffer storing recent voice commands (last 50-100).
    Does NOT store raw audio.
    """
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self._history = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()

    def record(
        self,
        transcript: str,
        intent: str,
        confidence: float,
        execution_status: str,
        stt_latency_ms: float = 0.0,
        intent_latency_ms: float = 0.0,
        total_latency_ms: float = 0.0
    ) -> CommandHistoryEntry:
        now = time.time()
        formatted = time.strftime("%H:%M:%S", time.localtime(now))
        entry = CommandHistoryEntry(
            timestamp=now,
            formatted_time=formatted,
            transcript=transcript,
            intent=intent,
            confidence=confidence,
            execution_status=execution_status,
            stt_latency_ms=stt_latency_ms,
            intent_latency_ms=intent_latency_ms,
            total_latency_ms=total_latency_ms
        )
        with self._lock:
            self._history.append(entry)
        return entry

    def get_recent(self, limit: int = 10) -> List[CommandHistoryEntry]:
        with self._lock:
            items = list(self._history)
            return items[-limit:]

    def get_last(self) -> Optional[CommandHistoryEntry]:
        with self._lock:
            if not self._history:
                return None
            return self._history[-1]
