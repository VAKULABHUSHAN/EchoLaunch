import time
import collections
import numpy as np
from typing import Callable, Optional
from src.audio.audio_buffer import PreRollBuffer, SpeechAccumulator
from src.utils.logger import setup_logger

logger = setup_logger("VAD")

class VoiceActivityDetector:
    """
    Voice Activity Detector with:
    - Adaptive noise floor baseline tracking
    - Rolling pre-roll audio buffer to prevent cutting off the first word
    - Fast silence timeout detection (default 0.45s)
    - Real-time throttled microphone activity meter (4-5 updates/sec)
    - Accurate speech start/end timestamps for latency profiling
    - Command acceptance pausing for self-listening prevention
    """
    def __init__(
        self,
        sample_rate: int = 16000,
        adaptive_threshold: bool = True,
        noise_floor_window: float = 2.0,
        sensitivity_multiplier: float = 2.0,
        minimum_threshold: float = 0.004,
        maximum_threshold: float = 0.05,
        silence_duration: float = 0.45,
        minimum_speech_duration: float = 0.20,
        max_recording_duration: float = 6.0,
        pre_roll_duration: float = 0.4,
        debug: bool = False
    ):
        self.sample_rate = sample_rate
        self.adaptive_threshold = adaptive_threshold
        self.noise_floor_window = noise_floor_window
        self.sensitivity_multiplier = sensitivity_multiplier
        self.minimum_threshold = minimum_threshold
        self.maximum_threshold = maximum_threshold
        self.silence_duration = silence_duration
        self.minimum_speech_duration = minimum_speech_duration
        self.max_recording_duration = max_recording_duration
        self.debug = debug

        # Pre-roll and speech accumulator buffers
        self.pre_roll = PreRollBuffer(sample_rate=sample_rate, max_duration_sec=pre_roll_duration)
        self.speech_accumulator = SpeechAccumulator(sample_rate=sample_rate, max_duration_sec=max_recording_duration)

        # Ambient noise floor tracking
        self._ambient_rms_history = collections.deque(maxlen=int(noise_floor_window * (sample_rate / 1024)))
        self._current_noise_floor = minimum_threshold
        self._current_threshold = max(minimum_threshold, minimum_threshold * sensitivity_multiplier)

        # State tracking
        self.is_speaking = False
        self.last_speech_time = 0.0
        self.speech_start_time = 0.0
        self._listening_enabled = True

        # Real-time meter throttling (4-5 times per second max)
        self._last_meter_time = 0.0
        self.meter_interval = 0.22

        # Callbacks: on_speech_start(), on_speech_end(audio, duration, t_start, t_end, t_finalized)
        self.on_speech_start: Optional[Callable[[], None]] = None
        self.on_speech_end: Optional[Callable[[np.ndarray, float, float, float, float], None]] = None

    def set_callbacks(
        self,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[np.ndarray, float, float, float, float], None]] = None
    ):
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

    def set_listening_enabled(self, enabled: bool):
        """Enable or disable accepting speech (used to prevent self-listening during TTS)."""
        self._listening_enabled = enabled
        if not enabled:
            self.flush()

    def flush(self):
        """Flushes the speech accumulator and pre-roll buffers."""
        self.is_speaking = False
        self.speech_accumulator.clear()
        self.pre_roll.clear()

    def _calculate_rms(self, audio: np.ndarray) -> float:
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio.astype(np.float32)**2)))

    def _update_noise_floor(self, rms: float):
        """Updates ambient noise floor tracking only during silence."""
        self._ambient_rms_history.append(rms)
        if len(self._ambient_rms_history) > 5 and self.adaptive_threshold:
            sorted_rms = sorted(self._ambient_rms_history)
            idx = int(len(sorted_rms) * 0.25)
            self._current_noise_floor = sorted_rms[idx]
            
            calculated_threshold = self._current_noise_floor * self.sensitivity_multiplier
            self._current_threshold = max(self.minimum_threshold, min(self.maximum_threshold, calculated_threshold))

    @property
    def current_threshold(self) -> float:
        return self._current_threshold

    @property
    def noise_floor(self) -> float:
        return self._current_noise_floor

    def process_frame(self, audio_chunk: np.ndarray):
        """
        Process an incoming audio chunk.
        """
        if not self._listening_enabled:
            return

        rms = self._calculate_rms(audio_chunk)
        now = time.time()

        # Throttled real-time debug meter (4-5 updates per second)
        if self.debug and (now - self._last_meter_time >= self.meter_interval):
            self._last_meter_time = now
            state_str = "SPEECH" if self.is_speaking else "Silence"
            print(f"[MIC] RMS: {rms:.4f} | Threshold: {self._current_threshold:.4f} | {state_str}", flush=True)

        if not self.is_speaking:
            # Silence state
            self.pre_roll.append(audio_chunk)
            self._update_noise_floor(rms)

            if rms >= self._current_threshold:
                # Transition to SPEECH_STARTED
                self.is_speaking = True
                self.speech_start_time = now
                self.last_speech_time = now
                
                # Prepend pre-roll audio so initial word syllables are never clipped
                pre_audio = self.pre_roll.get_audio()
                self.speech_accumulator.clear()
                if len(pre_audio) > 0:
                    self.speech_accumulator.append(pre_audio)
                self.speech_accumulator.append(audio_chunk)

                # Immediate user feedback
                print("\n[VOICE] Speech started 🎤", flush=True)

                if self.on_speech_start:
                    try:
                        self.on_speech_start()
                    except Exception as e:
                        logger.error(f"Error in on_speech_start callback: {e}")
        else:
            # Active speech state
            self.speech_accumulator.append(audio_chunk)

            if rms >= self._current_threshold:
                self.last_speech_time = now

            silence_elapsed = now - self.last_speech_time
            total_speech_duration = self.speech_accumulator.duration

            # Check if silence timeout reached OR max recording duration exceeded
            if silence_elapsed >= self.silence_duration or total_speech_duration >= self.max_recording_duration:
                self.is_speaking = False
                speech_end_actual = self.last_speech_time
                vad_finalized_time = now
                
                if total_speech_duration >= self.minimum_speech_duration:
                    print(f"[VOICE] Speech ended\n[VOICE] Duration: {total_speech_duration:.2f}s", flush=True)
                    
                    speech_audio = self.speech_accumulator.get_audio()
                    self.speech_accumulator.clear()
                    self.pre_roll.clear()

                    if self.on_speech_end:
                        try:
                            self.on_speech_end(
                                speech_audio,
                                total_speech_duration,
                                self.speech_start_time,
                                speech_end_actual,
                                vad_finalized_time
                            )
                        except Exception as e:
                            logger.error(f"Error in on_speech_end callback: {e}")
                else:
                    if self.debug:
                        print(f"[VOICE] Discarded short noise burst ({total_speech_duration:.2f}s < {self.minimum_speech_duration}s)")
                    self.speech_accumulator.clear()
                    self.pre_roll.clear()
