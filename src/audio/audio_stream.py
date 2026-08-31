import sounddevice as sd
import numpy as np
import threading
from typing import Callable, Optional
from src.utils.logger import setup_logger

logger = setup_logger("AudioStream")

class AudioStream:
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 1024, device: Optional[int] = None):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device = device
        self.stream: Optional[sd.InputStream] = None
        self.is_running = False
        self.callback: Optional[Callable[[np.ndarray], None]] = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time, status: sd.CallbackFlags):
        if status:
            logger.warning(f"Audio stream status: {status}")
        if self.callback and self.is_running:
            # Pass a copy of the single channel data (flattened)
            # Assuming mono or picking the first channel
            self.callback(indata[:, 0].copy())

    def start(self, callback: Callable[[np.ndarray], None]):
        """Starts the audio stream with the given callback."""
        if self.is_running:
            logger.warning("Stream is already running.")
            return

        self.callback = callback
        self.is_running = True

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=self.device,
                channels=1,
                callback=self._audio_callback
            )
            self.stream.start()
            
            device_info = sd.query_devices(self.device if self.device is not None else sd.default.device[0])
            logger.info(f"[LISTENING] Microphone active: {device_info['name']}")
        except Exception as e:
            self.is_running = False
            logger.error(f"Failed to start audio stream: {e}")
            raise

    def stop(self):
        """Stops the audio stream."""
        if not self.is_running:
            return
            
        self.is_running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        logger.info("Audio stream stopped.")

    @staticmethod
    def get_devices():
        """Returns a list of available audio devices."""
        return sd.query_devices()
