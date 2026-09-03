import collections
import threading
import numpy as np
from typing import List, Optional
from src.utils.logger import setup_logger

logger = setup_logger("AudioBuffer")

class PreRollBuffer:
    """
    Thread-safe circular pre-roll buffer holding the most recent audio chunks
    (e.g., 300ms - 500ms) to ensure leading syllables of speech are never cut off.
    """
    def __init__(self, sample_rate: int = 16000, max_duration_sec: float = 0.5):
        self.sample_rate = sample_rate
        self.max_duration_sec = max_duration_sec
        self.max_samples = int(sample_rate * max_duration_sec)
        self._lock = threading.Lock()
        self._chunks: collections.deque = collections.deque()
        self._current_samples = 0

    def append(self, chunk: np.ndarray):
        """Appends a 1D numpy array audio chunk and evicts oldest chunks exceeding capacity."""
        if chunk.ndim != 1:
            chunk = chunk.flatten()
        chunk_len = len(chunk)
        if chunk_len == 0:
            return

        with self._lock:
            self._chunks.append(chunk)
            self._current_samples += chunk_len
            while self._current_samples - len(self._chunks[0]) >= self.max_samples and len(self._chunks) > 1:
                evicted = self._chunks.popleft()
                self._current_samples -= len(evicted)

    def get_audio(self) -> np.ndarray:
        """Returns a single concatenated float32 numpy array of all audio in the pre-roll buffer."""
        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.float32)
            concatenated = np.concatenate(list(self._chunks)).astype(np.float32)
            # If slightly over max_samples, return the tail
            if len(concatenated) > self.max_samples:
                return concatenated[-self.max_samples:]
            return concatenated

    def clear(self):
        """Flushes the buffer."""
        with self._lock:
            self._chunks.clear()
            self._current_samples = 0


class SpeechAccumulator:
    """
    Thread-safe buffer that collects incoming audio chunks during active speech.
    Enforces maximum duration limits to prevent unbounded memory growth.
    """
    def __init__(self, sample_rate: int = 16000, max_duration_sec: float = 8.0):
        self.sample_rate = sample_rate
        self.max_duration_sec = max_duration_sec
        self.max_samples = int(sample_rate * max_duration_sec)
        self._lock = threading.Lock()
        self._chunks: List[np.ndarray] = []
        self._current_samples = 0

    def append(self, chunk: np.ndarray) -> bool:
        """
        Appends a chunk to the speech segment.
        Returns True if chunk was added, False if capacity reached.
        """
        if chunk.ndim != 1:
            chunk = chunk.flatten()
        chunk_len = len(chunk)
        if chunk_len == 0:
            return True

        with self._lock:
            if self._current_samples + chunk_len > self.max_samples:
                remaining = self.max_samples - self._current_samples
                if remaining > 0:
                    self._chunks.append(chunk[:remaining])
                    self._current_samples += remaining
                return False
            self._chunks.append(chunk)
            self._current_samples += chunk_len
            return True

    def get_audio(self) -> np.ndarray:
        """Returns the concatenated audio segment."""
        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.float32)
            return np.concatenate(self._chunks).astype(np.float32)

    @property
    def duration(self) -> float:
        """Returns the duration in seconds of collected speech so far."""
        with self._lock:
            return self._current_samples / float(self.sample_rate)

    @property
    def sample_count(self) -> int:
        with self._lock:
            return self._current_samples

    def clear(self):
        """Clears accumulated speech chunks."""
        with self._lock:
            self._chunks.clear()
            self._current_samples = 0
