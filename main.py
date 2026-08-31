import time
import threading
# pyrefly: ignore [missing-import]
import numpy as np
import sys
import argparse
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logger
from src.audio.audio_stream import AudioStream
from src.audio.speech_detector import SpeechDetector
from src.automation.workflow_manager import WorkflowManager
from src.ui.main_window import MainWindow

logger = setup_logger("Main")

class AppController:
    def __init__(self, debug=False):
        self.config = ConfigManager()
        
        # Audio config
        audio_cfg = self.config.get("audio", "sample_rate", 44100)
        self.chunk_size = self.config.get("audio", "chunk_size", 1024)
        energy_thresh = self.config.get("audio", "energy_threshold", 0.05)
        
        self.workflow_manager = WorkflowManager(self.config)
        
        # Setup Speech Detector
        self.detector = SpeechDetector(
            sample_rate=audio_cfg,
            energy_threshold=energy_thresh,
            silence_timeout=1.0,
            debug=debug
        )
        self.detector.set_callback(self.on_speech_recognized)
        
        self.stream = AudioStream(sample_rate=audio_cfg, chunk_size=self.chunk_size)
        
        # UI Setup
        self.window = MainWindow(
            config=self.config,
            start_audio_cb=self.start_audio,
            stop_audio_cb=self.stop_audio
        )
        
        self.last_action_text = "None"
        self.last_phrase = "Waiting..."
        self.is_running = True

    def on_speech_recognized(self, text):
        self.last_phrase = f'"{text}"'
        
        # Check if text matches a configured phrase exactly or contains it
        matched_command = None
        commands = self.config.config.get("commands", {})
        
        for cmd_key, cmd_cfg in commands.items():
            phrases_to_check = [cmd_key.lower()] + [alias.lower() for alias in cmd_cfg.get("aliases", [])]
            for phrase in phrases_to_check:
                if phrase in text:
                    matched_command = cmd_key
                    break
            if matched_command:
                break
        
        if matched_command:
            self.workflow_manager.trigger(matched_command)
            command_cfg = commands.get(matched_command)
            self.last_action_text = command_cfg.get("name", f"Workflow {matched_command}")
        else:
            self.last_action_text = f"Unrecognized phrase"
            
        self.window.update_dashboard(0, 0, self.last_phrase, self.last_action_text)

    def audio_callback(self, indata: np.ndarray):
        # The stream callback provides audio chunks
        self.detector.analyze_chunk(indata)
        
        # Extract basic mic level (RMS) for UI visualization
        rms = np.sqrt(np.mean(indata**2))
        
        # Update UI safely
        self.window.update_dashboard(rms, 0.0, self.last_phrase, self.last_action_text)

    def start_audio(self):
        try:
            self.stream.start(self.audio_callback)
        except Exception as e:
            logger.error(f"Error starting audio: {e}")

    def stop_audio(self):
        self.stream.stop()

    def run(self):
        self.start_audio()
        
        # Start UI mainloop
        self.window.mainloop()
        
        self.is_running = False
        self.stop_audio()

def main():
    parser = argparse.ArgumentParser(description="CLAPOS - Acoustic Gesture Desktop Automation")
    parser.add_argument("--calibrate", action="store_true", help="Run calibration mode")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode with extra logging")
    parser.add_argument("--test", action="store_true", help="Run test mode with synthetic audio")
    args = parser.parse_args()

    if args.calibrate:
        config = ConfigManager()
        stream = AudioStream()
        from src.audio.calibrator import Calibrator
        calibrator = Calibrator(config, stream)
        calibrator.run_calibration()
        return

    app = AppController(debug=args.debug)
    app.run()

if __name__ == "__main__":
    main()
