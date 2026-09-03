import os
import sys
import time
import sounddevice as sd
import numpy as np
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logger
from src.core.state_manager import StateManager, AssistantState
from src.core.command_history import CommandHistory
from src.core.intent_engine import IntentEngine
from src.core.event_router import EventRouter
from src.audio.audio_manager import AudioManager
from src.audio.voice_activity_detector import VoiceActivityDetector
from src.voice.activation_manager import ActivationManager
from src.voice.transcript_validator import TranscriptValidator
from src.voice.speech_recognizer import FasterWhisperRecognizer, TranscriptionResult
from src.voice.tts_engine import TTSEngine
from src.automation.workflow_manager import WorkflowManager

logger = setup_logger("Assistant")

try:
    "✓".encode(sys.stdout.encoding or "utf-8")
    CHECKMARK = "✓"
except Exception:
    CHECKMARK = "[OK]"


class ClaposAssistant:
    """
    CLAPOS V3 Voice Assistant Orchestrator.
    Optimized for high-responsiveness, real-time microphone diagnostics,
    accurate latency profiling, and short-command desktop workflows.
    """
    def __init__(self, config_path: str = "config/config.json", debug: bool = False):
        self.debug = debug
        self.config_path = config_path
        self.is_running = False

        print("\n[STARTUP] Initializing CLAPOS\n")

        # 1. Config Check
        self.config = ConfigManager(config_path=config_path, validate=True)
        print(f"[CHECK] Configuration loaded {CHECKMARK}")

        # 2. State & History
        self.state_manager = StateManager(debug=debug)
        self.command_history = CommandHistory(capacity=100)

        # 3. Audio & VAD Config
        audio_cfg = self.config.get_section("audio", {})
        sample_rate = int(audio_cfg.get("sample_rate", 16000))
        chunk_size = int(audio_cfg.get("chunk_size", 1024))
        device_idx = audio_cfg.get("device")
        reconnect_int = float(audio_cfg.get("reconnect_interval", 2.0))
        max_reconnect = int(audio_cfg.get("max_reconnect_attempts", 5))

        vad_cfg = self.config.get_section("vad", {})
        self.vad = VoiceActivityDetector(
            sample_rate=sample_rate,
            adaptive_threshold=bool(vad_cfg.get("adaptive_threshold", True)),
            noise_floor_window=float(vad_cfg.get("noise_floor_window", 2.0)),
            sensitivity_multiplier=float(vad_cfg.get("sensitivity_multiplier", 2.0)),
            minimum_threshold=float(vad_cfg.get("minimum_threshold", 0.004)),
            maximum_threshold=float(vad_cfg.get("maximum_threshold", 0.05)),
            silence_duration=float(vad_cfg.get("silence_duration", 0.45)),
            minimum_speech_duration=float(vad_cfg.get("minimum_speech_duration", 0.20)),
            max_recording_duration=float(vad_cfg.get("max_recording_duration", 6.0)),
            pre_roll_duration=float(vad_cfg.get("pre_roll_duration", 0.4)),
            debug=debug
        )

        self.audio_manager = AudioManager(
            sample_rate=sample_rate,
            chunk_size=chunk_size,
            device=device_idx,
            reconnect_interval=reconnect_int,
            max_reconnect_attempts=max_reconnect
        )
        print(f"[CHECK] Microphone available {CHECKMARK}")

        # 4. Speech Recognition (Pre-loaded before entering LISTENING state)
        voice_cfg = self.config.get_section("voice", {})
        model_name = voice_cfg.get("model", "base.en")
        device_type = voice_cfg.get("device", "cpu")
        compute_type = voice_cfg.get("compute_type", "int8")

        self.speech_recognizer = FasterWhisperRecognizer(
            model_name=model_name,
            device=device_type,
            compute_type=compute_type,
            debug=debug
        )
        self.speech_recognizer.initialize_model()
        print(f"[CHECK] Faster Whisper model loaded {CHECKMARK}")

        # 5. Validation & Activation
        tr_cfg = self.config.get_section("transcription", {})
        self.validator = TranscriptValidator(
            min_log_probability=float(tr_cfg.get("min_log_probability", -1.0)),
            max_no_speech_probability=float(tr_cfg.get("max_no_speech_probability", 0.6)),
            minimum_text_length=int(tr_cfg.get("minimum_text_length", 2))
        )
        self.activation_manager = ActivationManager(mode=voice_cfg.get("mode", "CONTINUOUS_COMMAND"))

        # 6. TTS Engine & Self-Listening Sequence Hooks
        tts_cfg = self.config.get_section("tts", {})
        rate = int(tts_cfg.get("rate", 175))
        volume = float(tts_cfg.get("volume", 1.0))
        cooldown = float(tts_cfg.get("cooldown_duration", 0.3))

        self.tts = TTSEngine(
            rate=rate,
            volume=volume,
            cooldown_duration=cooldown,
            debug=debug
        )
        self._setup_self_listening_hooks()
        print(f"[CHECK] TTS engine initialized {CHECKMARK}")

        # 7. Workflow Manager
        self.workflow_manager = WorkflowManager(
            config_manager=self.config,
            debug=debug
        )
        print(f"[CHECK] Workflow configuration loaded {CHECKMARK}\n")

        # 8. Intent Engine & Event Router
        intent_cfg = self.config.get_section("intent", {})
        conv_th = float(intent_cfg.get("conversation_threshold", 0.65))
        action_th = float(intent_cfg.get("action_threshold", 0.82))

        self.intent_engine = IntentEngine(
            conversation_threshold=conv_th,
            action_threshold=action_th
        )

        self.event_router = EventRouter(
            config_manager=self.config,
            tts_engine=self.tts,
            workflow_manager=self.workflow_manager,
            command_history=self.command_history,
            debug=debug
        )

        # Connect pipeline callbacks
        self.vad.set_callbacks(
            on_speech_start=self._on_speech_start,
            on_speech_end=self._on_speech_end
        )
        self.speech_recognizer.set_callback(self._on_transcription_complete)

    def _setup_self_listening_hooks(self):
        """Wires up the strict self-listening protection sequence."""
        def pre_speech():
            self.state_manager.set_speaking(True)
            self.vad.set_listening_enabled(False)
            self.state_manager.transition_to(AssistantState.SPEAKING)

        def flush_buffers():
            self.vad.flush()
            self.speech_recognizer.flush()

        def post_speech():
            self.vad.flush()
            self.vad.set_listening_enabled(True)
            self.state_manager.set_speaking(False)
            self.state_manager.transition_to(AssistantState.LISTENING)

        self.tts.set_hooks(
            pre_speech_hook=pre_speech,
            flush_hook=flush_buffers,
            post_speech_hook=post_speech
        )

    def _on_speech_start(self):
        if not self.state_manager.is_speaking:
            self.state_manager.transition_to(AssistantState.PROCESSING)

    def _on_speech_end(
        self,
        audio: np.ndarray,
        duration: float,
        speech_start_time: float,
        speech_end_time: float,
        vad_finalized_time: float
    ):
        if self.state_manager.is_speaking:
            return
        self.speech_recognizer.enqueue_audio(
            audio,
            speech_start_time=speech_start_time,
            speech_end_time=speech_end_time,
            vad_finalized_time=vad_finalized_time
        )

    def _on_transcription_complete(
        self,
        result: TranscriptionResult,
        speech_start_time: float,
        speech_end_time: float,
        vad_finalized_time: float,
        stt_start_time: float,
        stt_end_time: float
    ):
        if self.state_manager.is_speaking:
            return

        raw_text = result.text

        # 1. Validate transcript against Whisper hallucinations
        is_valid, cleaned_text, reason = self.validator.validate(
            raw_text,
            avg_logprob=result.avg_logprob,
            no_speech_prob=result.no_speech_prob
        )

        if not is_valid:
            if self.debug:
                print(f"[VALIDATION] Rejected transcript '{raw_text}': {reason}")
            self.state_manager.transition_to(AssistantState.LISTENING)
            return

        print(f"\n[TRANSCRIPT]\n\"{cleaned_text}\"")

        # 2. Check Activation Manager mode
        if not self.activation_manager.should_process_speech():
            self.state_manager.transition_to(AssistantState.LISTENING)
            return

        # 3. Intent Engine
        self.state_manager.transition_to(AssistantState.THINKING)
        intent_start = time.time()
        intent_res = self.intent_engine.parse_intent(cleaned_text)
        intent_end = time.time()

        print(f"\n[INTENT] {intent_res.intent}")
        print(f"[CONFIDENCE] {intent_res.confidence:.2f}")

        # 4. Route Intent (Response & Automation)
        stt_latency_ms = result.inference_time_ms
        intent_latency_ms = (intent_end - intent_start) * 1000
        vad_delay_ms = (vad_finalized_time - speech_end_time) * 1000
        speech_duration = speech_end_time - speech_start_time

        resp_queue_ms = self.event_router.route_intent(
            intent_res,
            stt_latency_ms=stt_latency_ms,
            intent_latency_ms=intent_latency_ms
        )

        total_post_speech_ms = vad_delay_ms + stt_latency_ms + intent_latency_ms + resp_queue_ms

        print(f"\n[PERFORMANCE]")
        print(f"Speech Duration: {speech_duration:.2f}s")
        print(f"VAD Finalization Delay: {vad_delay_ms:.0f}ms")
        print(f"STT Latency: {stt_latency_ms:.0f}ms")
        print(f"Intent Latency: {intent_latency_ms:.0f}ms")
        print(f"Response Queue Latency: {resp_queue_ms:.0f}ms")
        print(f"Total Post-Speech Latency: {total_post_speech_ms:.0f}ms\n")

        # Reset activation for push-to-talk / wake-word modes
        self.activation_manager.reset_after_command()

        if not self.state_manager.is_speaking:
            self.state_manager.transition_to(AssistantState.LISTENING)

    def start(self):
        """Starts all assistant services and enters LISTENING state explicitly."""
        self.is_running = True

        # Start workers
        self.tts.start()
        self.workflow_manager.start()
        self.speech_recognizer.start()

        # Start audio stream
        self.audio_manager.start(self.vad.process_frame)

        # Print active device and VAD info
        dev_info = self.audio_manager.get_active_device_info()
        print(f"[ACTIVE DEVICE]\n{dev_info['name']}\nInput Channels: {dev_info['channels']}\nSample Rate: {dev_info['sample_rate']} Hz\n")
        print(f"[VAD] Initial noise floor: {self.vad.noise_floor:.4f}")
        print(f"[VAD] Current threshold: {self.vad.current_threshold:.4f}\n")

        print("[INFO] Audio stream started")
        print("[INFO] VAD active")
        print("[INFO] STT worker active\n")

        # Explicitly announce listening state
        self.state_manager.transition_to(AssistantState.LISTENING)
        print("[STATE] LISTENING")
        print("[VOICE] Waiting for speech...\n")

        # Speak startup greeting if configured
        startup_greeting = self.config.get("assistant", "startup_greeting", True)
        startup_msg = self.config.get("assistant", "startup_message", "CLAPOS is online.")
        if startup_greeting and startup_msg:
            self.tts.speak(startup_msg)

    def run_forever(self):
        """Main blocking loop that catches interrupts gracefully."""
        self.start()
        try:
            while self.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[STOP REQUESTED] Shutting down CLAPOS gracefully...")
        finally:
            self.stop()

    def stop(self):
        """Clean shutdown sequence across all worker threads and streams."""
        if not self.is_running:
            return
        self.is_running = False

        print("[STOP] Stopping audio capture...")
        self.audio_manager.stop()
        self.vad.flush()

        print("[STOP] Stopping STT worker...")
        self.speech_recognizer.stop()

        print("[STOP] Stopping TTS worker...")
        self.tts.stop()

        print("[STOP] Stopping workflow worker...")
        self.workflow_manager.stop()

        self.state_manager.transition_to(AssistantState.PAUSED)
        print("[STOP] CLAPOS successfully stopped.")
