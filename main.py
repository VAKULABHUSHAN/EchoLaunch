import argparse
import signal
import sys
import time
import numpy as np

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.audio.audio_manager import AudioManager
from src.audio.voice_activity_detector import VoiceActivityDetector
from src.voice.speech_recognizer import FasterWhisperRecognizer
from src.utils.config_manager import ConfigManager
from src.core.assistant import ClaposAssistant


def run_list_devices():
    """Lists all available microphone input devices."""
    devices = AudioManager.list_input_devices()
    print("\n[AUDIO INPUT DEVICES]\n")
    for d in devices:
        default_tag = " (DEFAULT)" if d["is_default"] else ""
        print(f"  [{d['index']}] {d['name']}{default_tag}")
        print(f"      Channels: {d['channels']}, Default Rate: {d['default_samplerate']} Hz\n")


def run_mic_test(config_path: str = "config/config.json"):
    """
    Dedicated microphone and VAD test mode.
    Does NOT load Whisper, TTS, or workflow engines.
    """
    cfg = ConfigManager(config_path=config_path, validate=True)
    audio_cfg = cfg.get_section("audio", {})
    vad_cfg = cfg.get_section("vad", {})

    sample_rate = int(audio_cfg.get("sample_rate", 16000))
    chunk_size = int(audio_cfg.get("chunk_size", 1024))
    device_idx = audio_cfg.get("device")

    print("\n" + "=" * 40)
    print("       CLAPOS MICROPHONE TEST")
    print("=" * 40 + "\n")

    audio_manager = AudioManager(
        sample_rate=sample_rate,
        chunk_size=chunk_size,
        device=device_idx
    )

    vad = VoiceActivityDetector(
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
        debug=False
    )

    def on_speech_start():
        print("  >>> Speech detected! 🎤")

    def on_speech_end(audio, duration, t0, t1, t2):
        print(f"  >>> Speech ended (Duration: {duration:.2f}s)\n")

    vad.set_callbacks(on_speech_start=on_speech_start, on_speech_end=on_speech_end)

    # Meter state
    last_print = 0.0

    def process_frame(chunk: np.ndarray):
        nonlocal last_print
        vad.process_frame(chunk)
        now = time.time()
        if now - last_print >= 0.20:
            last_print = now
            rms = vad._calculate_rms(chunk)
            bar_len = min(int(rms * 500), 30)
            bar = "█" * max(bar_len, 1)
            tag = "SPEECH" if vad.is_speaking else ""
            print(f"RMS: {rms:.4f}  {bar:<30} {tag}", flush=True)

    audio_manager.start(process_frame)
    dev_info = audio_manager.get_active_device_info()

    print(f"Microphone:\n{dev_info['name']}\n")
    print(f"Sample Rate:\n{sample_rate} Hz\n")
    print(f"Chunk Size:\n{chunk_size}\n")
    print("Listening... (Press Ctrl+C to stop)\n")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping microphone test...")
    finally:
        audio_manager.stop()
        print("Microphone test stopped.")


def run_benchmark():
    """
    Benchmarks tiny.en vs base.en STT latency on typical desktop assistant phrases.
    """
    print("\n" + "=" * 40)
    print("       MODEL BENCHMARK (tiny.en vs base.en)")
    print("=" * 40 + "\n")

    test_models = ["tiny.en", "base.en"]
    # Synthesize test audio bursts (1.0 second silence + tone + silence)
    sr = 16000
    t = np.linspace(0, 0.8, int(sr * 0.8), False)
    test_audio = (np.sin(440 * t * 2 * np.pi) * 0.1).astype(np.float32)

    for model_name in test_models:
        print(f"Loading '{model_name}' for benchmark...")
        recognizer = FasterWhisperRecognizer(model_name=model_name, device="cpu", compute_type="int8")
        recognizer.initialize_model()

        latencies = []
        for _ in range(5):
            res = recognizer.transcribe(test_audio)
            latencies.append(res.inference_time_ms)

        avg_lat = np.mean(latencies[1:])  # drop warmup
        print(f"\n[{model_name}]")
        print(f"Average STT Latency: {avg_lat:.0f}ms")
        print(f"Min Latency: {min(latencies):.0f}ms")
        print(f"Max Latency: {max(latencies):.0f}ms\n" + "-" * 30)


def main():
    parser = argparse.ArgumentParser(description="CLAPOS V3 — Voice-First Personal Desktop Assistant")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging, real-time meter, and latency telemetry")
    parser.add_argument("--mic-test", action="store_true", help="Run standalone microphone and VAD VU meter test")
    parser.add_argument("--list-devices", action="store_true", help="List all available audio input devices")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark STT latency between tiny.en and base.en")
    parser.add_argument("--config", type=str, default="config/config.json", help="Path to configuration file")
    args = parser.parse_args()

    if args.list_devices:
        run_list_devices()
        return

    if args.mic_test:
        run_mic_test(config_path=args.config)
        return

    if args.benchmark:
        run_benchmark()
        return

    assistant = ClaposAssistant(config_path=args.config, debug=args.debug)

    def sig_handler(signum, frame):
        assistant.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    assistant.run_forever()


if __name__ == "__main__":
    main()
