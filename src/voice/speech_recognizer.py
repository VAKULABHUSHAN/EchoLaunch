import abc
import time
import queue
import threading
import numpy as np
from dataclasses import dataclass
from typing import Callable, Optional, Tuple
from faster_whisper import WhisperModel
from src.utils.logger import setup_logger

logger = setup_logger("SpeechRecognizer")

@dataclass
class TranscriptionResult:
    text: str
    avg_logprob: float
    no_speech_prob: float
    duration: float
    inference_time_ms: float

class SpeechRecognizer(abc.ABC):
    """Abstract interface for speech recognition engines."""
    @abc.abstractmethod
    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
        pass


class FasterWhisperRecognizer(SpeechRecognizer):
    """
    Faster-Whisper speech recognition engine optimized for short voice commands.
    - Single concurrent STT worker on CPU to prevent latency spikes.
    - Uses beam_size=1, best_of=1, temperature=0.0, condition_on_previous_text=False.
    - Bounded queue with drop-oldest overflow policy.
    - Tracks detailed end-to-end timing across the pipeline.
    """
    def __init__(
        self,
        model_name: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        queue_size: int = 5,
        debug: bool = False
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.queue_size = queue_size
        self.debug = debug

        # Dedicated bounded queue: (audio, t_start, t_end, t_finalized)
        self._stt_queue = queue.Queue(maxsize=self.queue_size)

        self.model: Optional[WhisperModel] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._is_running = False

        # Callback: (result, t_start, t_end, t_finalized, t_stt_start, t_stt_end)
        self.on_transcription_complete: Optional[Callable[[TranscriptionResult, float, float, float, float, float], None]] = None

    def initialize_model(self):
        """Loads the model into memory. Called during startup health check."""
        if self.model is None:
            logger.info(f"Loading Faster-Whisper model '{self.model_name}' on {self.device} ({self.compute_type})...")
            start = time.time()
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type
            )
            elapsed = (time.time() - start) * 1000
            logger.info(f"Faster-Whisper model loaded in {elapsed:.0f}ms.")

    def set_callback(self, callback: Callable[[TranscriptionResult, float, float, float, float, float], None]):
        self.on_transcription_complete = callback

    def start(self):
        """Starts the dedicated STT worker thread."""
        if self._is_running:
            return

        if self.model is None:
            self.initialize_model()

        self._is_running = True
        self._worker_thread = threading.Thread(target=self._stt_worker, daemon=False, name="STTWorker")
        self._worker_thread.start()

    def enqueue_audio(
        self,
        audio: np.ndarray,
        speech_start_time: float,
        speech_end_time: float,
        vad_finalized_time: float
    ):
        """
        Enqueues an audio segment for transcription.
        If queue is full, drops the oldest segment to maintain real-time responsiveness.
        """
        if not self._is_running:
            return

        item = (audio, speech_start_time, speech_end_time, vad_finalized_time)

        try:
            self._stt_queue.put_nowait(item)
        except queue.Full:
            try:
                self._stt_queue.get_nowait()
                self._stt_queue.task_done()
                if self.debug:
                    print("[QUEUE] STT queue full — dropped oldest segment")
            except queue.Empty:
                pass
            try:
                self._stt_queue.put_nowait(item)
            except queue.Full:
                pass

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
        """Synchronous transcription optimized specifically for short voice commands."""
        if self.model is None:
            self.initialize_model()

        start_time = time.time()
        
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Low-latency parameter set for short commands with domain vocabulary bias
        segments, info = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            initial_prompt="Dev mode, game mode, entertainment mode, developer mode, gaming mode, youtube, what time is it, hello.",
            vad_filter=False
        )

        texts = []
        logprobs = []
        no_speech_probs = []

        for seg in segments:
            texts.append(seg.text)
            logprobs.append(seg.avg_logprob)
            no_speech_probs.append(getattr(seg, 'no_speech_prob', 0.0))

        inference_time_ms = (time.time() - start_time) * 1000
        full_text = " ".join(texts).strip()
        avg_logprob = float(np.mean(logprobs)) if logprobs else 0.0
        no_speech_prob = float(np.mean(no_speech_probs)) if no_speech_probs else getattr(info, 'all_language_probs', 0.0)

        return TranscriptionResult(
            text=full_text,
            avg_logprob=avg_logprob,
            no_speech_prob=no_speech_prob,
            duration=len(audio) / 16000.0,
            inference_time_ms=inference_time_ms
        )

    def _stt_worker(self):
        """Worker loop processing speech segments sequentially (concurrency = 1)."""
        logger.info("STT worker loop active.")
        while self._is_running:
            try:
                item = self._stt_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is None:
                self._stt_queue.task_done()
                break

            audio, t_start, t_end, t_finalized = item

            try:
                print("[STT] Processing...")
                t_stt_start = time.time()
                result = self.transcribe(audio)
                t_stt_end = time.time()
                print(f"[STT] Completed in {result.inference_time_ms:.0f}ms")

                if self.on_transcription_complete:
                    self.on_transcription_complete(result, t_start, t_end, t_finalized, t_stt_start, t_stt_end)

            except Exception as e:
                logger.error(f"Error during transcription worker execution: {e}")
            finally:
                self._stt_queue.task_done()

        logger.info("STT worker thread stopped.")

    def flush(self):
        """Discards all pending audio in the STT queue."""
        while not self._stt_queue.empty():
            try:
                self._stt_queue.get_nowait()
                self._stt_queue.task_done()
            except (queue.Empty, ValueError):
                break

    def stop(self):
        """Stops the STT worker thread cleanly."""
        self._is_running = False
        self.flush()
        try:
            self._stt_queue.put_nowait(None)
        except queue.Full:
            pass
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
