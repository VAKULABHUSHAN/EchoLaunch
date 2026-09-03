import sounddevice as sd
import numpy as np
import threading
import queue
import time
from typing import Callable, Optional, Dict, Any, List
from src.utils.logger import setup_logger

logger = setup_logger("AudioManager")

class AudioManager:
    """
    Centralized microphone audio stream manager.
    Features:
    - Ultra-lightweight non-blocking InputStream callback (puts chunks directly into queue)
    - Dedicated audio worker thread to decouple hardware capture from VAD / processing
    - Automatic error detection and reconnection with exponential backoff
    - Device diagnostics and listing support
    """
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
        device: Optional[int] = None,
        reconnect_interval: float = 2.0,
        max_reconnect_attempts: int = 5,
        queue_size: int = 100
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device = device
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.queue_size = queue_size

        self.stream: Optional[sd.InputStream] = None
        self.is_running = False
        self.callback: Optional[Callable[[np.ndarray], None]] = None

        self._audio_queue = queue.Queue(maxsize=queue_size)
        self._worker_thread: Optional[threading.Thread] = None
        self._reconnecting = False
        self._lock = threading.Lock()

    def _stream_callback(self, indata: np.ndarray, frames: int, time_info, status: sd.CallbackFlags):
        """Hardware callback: must return immediately without blocking or heavy computation."""
        if not self.is_running or self._reconnecting:
            return

        # Fast 1D mono slice
        mono_chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()

        try:
            self._audio_queue.put_nowait(mono_chunk)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.task_done()
            except (queue.Empty, ValueError):
                pass
            try:
                self._audio_queue.put_nowait(mono_chunk)
            except queue.Full:
                pass

    def _audio_worker(self):
        """Dedicated background thread processing chunks from the audio queue."""
        while self.is_running:
            try:
                chunk = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if chunk is None:
                self._audio_queue.task_done()
                break

            if self.callback:
                try:
                    self.callback(chunk)
                except Exception as e:
                    logger.error(f"Error in audio processing callback: {e}")

            self._audio_queue.task_done()

    def start(self, callback: Callable[[np.ndarray], None]):
        """Starts the audio capture stream and worker thread."""
        with self._lock:
            if self.is_running:
                logger.warning("AudioManager is already running.")
                return

            self.callback = callback
            self.is_running = True

            # Start worker thread
            self._worker_thread = threading.Thread(target=self._audio_worker, daemon=True, name="AudioWorker")
            self._worker_thread.start()

            self._start_stream()

    def _start_stream(self):
        """Internal helper to initialize and start the InputStream."""
        target_device = self.device
        try:
            if target_device is not None:
                try:
                    sd.query_devices(target_device, 'input')
                except Exception:
                    logger.warning(f"Configured device {target_device} unavailable. Falling back to system default.")
                    target_device = None

            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=target_device,
                channels=1,
                dtype='float32',
                callback=self._stream_callback
            )
            self.stream.start()

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            if self.is_running:
                self._trigger_reconnect()
            else:
                raise

    def get_active_device_info(self) -> Dict[str, Any]:
        """Returns details about the active microphone device."""
        if self.stream and self.stream.active:
            try:
                info = sd.query_devices(self.stream.device)
                return {
                    "name": info.get("name", "Unknown"),
                    "index": self.stream.device,
                    "channels": info.get("max_input_channels", 1),
                    "sample_rate": self.sample_rate
                }
            except Exception:
                pass
        return {"name": "Default Microphone", "index": None, "channels": 1, "sample_rate": self.sample_rate}

    @staticmethod
    def list_input_devices() -> List[Dict[str, Any]]:
        """Queries and returns all available audio input devices."""
        devices = sd.query_devices()
        input_devs = []
        default_idx = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else None

        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                is_default = (idx == default_idx)
                input_devs.append({
                    "index": idx,
                    "name": dev.get("name"),
                    "channels": dev.get("max_input_channels"),
                    "default_samplerate": dev.get("default_samplerate"),
                    "is_default": is_default
                })
        return input_devs

    def _trigger_reconnect(self):
        """Spawns a thread to attempt automatic stream recovery with backoff."""
        if self._reconnecting:
            return
        self._reconnecting = True
        thread = threading.Thread(target=self._reconnect_worker, daemon=True)
        thread.start()

    def _reconnect_worker(self):
        logger.warning("Attempting automatic microphone stream recovery...")
        attempt = 0
        backoff = self.reconnect_interval

        while self.is_running and attempt < self.max_reconnect_attempts:
            attempt += 1
            logger.info(f"Microphone reconnection attempt {attempt}/{self.max_reconnect_attempts} (waiting {backoff:.1f}s)...")
            time.sleep(backoff)

            with self._lock:
                try:
                    if self.stream:
                        try:
                            self.stream.stop()
                            self.stream.close()
                        except Exception:
                            pass
                        self.stream = None

                    self.device = None
                    self._start_stream()
                    logger.info("Microphone stream successfully recovered!")
                    self._reconnecting = False
                    return
                except Exception as e:
                    logger.error(f"Reconnection attempt {attempt} failed: {e}")
                    backoff = min(backoff * 1.5, 10.0)

        logger.error(f"Microphone recovery failed after {self.max_reconnect_attempts} attempts.")
        self._reconnecting = False

    def stop(self):
        """Stops the audio stream and worker thread."""
        with self._lock:
            self.is_running = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                    logger.debug(f"Error closing stream: {e}")
                self.stream = None

            try:
                self._audio_queue.put_nowait(None)
            except Exception:
                pass

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)

    def is_healthy(self) -> bool:
        """Returns True if the stream is active and not currently reconnecting."""
        return bool(self.is_running and self.stream and self.stream.active and not self._reconnecting)
