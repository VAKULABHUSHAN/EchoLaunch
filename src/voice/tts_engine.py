import queue
import threading
import time
import sys
from typing import Callable, Optional
from src.utils.logger import setup_logger

logger = setup_logger("TTSEngine")

class TTSEngine:
    """
    Text-to-Speech Engine for Windows and cross-platform.
    - Uses native Windows SAPI.SpVoice with CoInitialize for instant, reliable audio output through speakers.
    - Falls back to pyttsx3 on non-Windows or if SAPI is unavailable.
    - Runs in a dedicated background worker thread with a bounded speech queue.
    - Never blocks the microphone listening thread.
    - Implements the complete self-listening protection sequence:
        1. TTS Starts
        2. Pause command acceptance
        3. Flush pending audio buffers
        4. Play speech through speakers
        5. Speech finishes
        6. Wait cooldown (e.g. 300ms)
        7. Flush audio buffers again
        8. Resume command acceptance
    """
    def __init__(
        self,
        rate: int = 175,
        volume: float = 1.0,
        voice_id: Optional[str] = None,
        cooldown_duration: float = 0.3,
        queue_size: int = 10,
        debug: bool = False
    ):
        self.rate = rate
        self.volume = volume
        self.voice_id = voice_id
        self.cooldown_duration = cooldown_duration
        self.queue_size = queue_size
        self.debug = debug

        self._speech_queue = queue.Queue(maxsize=queue_size)
        self._is_running = False
        self._worker_thread: Optional[threading.Thread] = None

        # Hooks to coordinate with Assistant / AudioManager / VAD
        self.pre_speech_hook: Optional[Callable[[], None]] = None
        self.post_speech_hook: Optional[Callable[[], None]] = None
        self.flush_hook: Optional[Callable[[], None]] = None

        self._is_speaking = False

    def set_hooks(
        self,
        pre_speech_hook: Optional[Callable[[], None]] = None,
        post_speech_hook: Optional[Callable[[], None]] = None,
        flush_hook: Optional[Callable[[], None]] = None
    ):
        self.pre_speech_hook = pre_speech_hook
        self.post_speech_hook = post_speech_hook
        self.flush_hook = flush_hook

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def start(self):
        """Starts the background TTS worker thread."""
        if self._is_running:
            return
        self._is_running = True
        self._worker_thread = threading.Thread(target=self._tts_worker, daemon=False, name="TTSWorker")
        self._worker_thread.start()

    def speak(self, text: str, on_complete: Optional[Callable[[], None]] = None):
        """
        Enqueues text for verbal response. Non-blocking.
        If the queue is full, drops the oldest pending message to avoid stale speech.
        """
        if not self._is_running or not text:
            return

        item = (text, on_complete)
        try:
            self._speech_queue.put_nowait(item)
        except queue.Full:
            try:
                self._speech_queue.get_nowait()
                self._speech_queue.task_done()
                if self.debug:
                    logger.debug("[QUEUE] TTS queue full — dropped oldest speech item")
            except queue.Empty:
                pass
            try:
                self._speech_queue.put_nowait(item)
            except queue.Full:
                pass

    def _tts_worker(self):
        """Dedicated worker thread managing speech playback through laptop speakers."""
        use_sapi = False
        sapi_voice = None
        pyttsx_engine = None

        # Attempt native Windows SAPI5 first for 100% reliable hardware output
        if sys.platform == "win32":
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
                # Map rate (175 wpm is standard ~ 1 in SAPI -10 to 10 scale)
                sapi_rate = int((self.rate - 175) / 25)
                sapi_voice.Rate = max(-10, min(10, sapi_rate))
                sapi_voice.Volume = int(max(0.0, min(1.0, self.volume)) * 100)
                use_sapi = True
                logger.info("TTS Engine initialized using native Windows SAPI.SpVoice.")
            except Exception as e:
                logger.warning(f"Could not initialize Windows SAPI.SpVoice, falling back to pyttsx3: {e}")

        if not use_sapi:
            try:
                import pyttsx3
                pyttsx_engine = pyttsx3.init()
                pyttsx_engine.setProperty('rate', self.rate)
                pyttsx_engine.setProperty('volume', self.volume)
                if self.voice_id:
                    pyttsx_engine.setProperty('voice', self.voice_id)
                logger.info("TTS Engine initialized using pyttsx3.")
            except Exception as e:
                logger.error(f"Failed to initialize pyttsx3 in TTS worker: {e}")
                return

        while self._is_running:
            try:
                item = self._speech_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is None:
                self._speech_queue.task_done()
                break

            text, on_complete = item

            try:
                self._is_speaking = True

                # 1. Pause command acceptance
                if self.pre_speech_hook:
                    try:
                        self.pre_speech_hook()
                    except Exception as e:
                        logger.error(f"Error in pre_speech_hook: {e}")

                # 2. Flush pending audio buffers
                if self.flush_hook:
                    try:
                        self.flush_hook()
                    except Exception as e:
                        logger.error(f"Error in flush_hook: {e}")

                # 3. Speak response directly out of laptop speakers
                if self.debug:
                    logger.debug(f"[TTS] Speaking aloud: \"{text}\"")

                if use_sapi and sapi_voice:
                    # SAPI synchronous speech (0 flag = SVSFDefault, blocks worker until speech is spoken)
                    sapi_voice.Speak(text, 0)
                elif pyttsx_engine:
                    pyttsx_engine.say(text)
                    pyttsx_engine.runAndWait()

                # 4. Wait configured cooldown after speech ends
                if self.cooldown_duration > 0:
                    time.sleep(self.cooldown_duration)

                # 5. Flush audio buffers again
                if self.flush_hook:
                    try:
                        self.flush_hook()
                    except Exception as e:
                        logger.error(f"Error in flush_hook (post-speech): {e}")

                # 6. Resume command acceptance
                if self.post_speech_hook:
                    try:
                        self.post_speech_hook()
                    except Exception as e:
                        logger.error(f"Error in post_speech_hook: {e}")

                if on_complete:
                    try:
                        on_complete()
                    except Exception as e:
                        logger.error(f"Error in TTS on_complete callback: {e}")

            except Exception as e:
                logger.error(f"Error during TTS speech generation: {e}")
            finally:
                self._is_speaking = False
                self._speech_queue.task_done()

        if use_sapi:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
        elif pyttsx_engine:
            try:
                pyttsx_engine.stop()
            except Exception:
                pass

        logger.info("TTS worker thread stopped.")

    def stop(self):
        """Stops the TTS worker thread cleanly."""
        self._is_running = False
        try:
            self._speech_queue.put_nowait(None)
        except queue.Full:
            pass
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
