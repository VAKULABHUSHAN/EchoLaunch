import time
import sys
# pyrefly: ignore [missing-import]
import numpy as np
from src.audio.audio_stream import AudioStream
from src.audio.feature_extractor import FeatureExtractor
from src.utils.logger import setup_logger
from src.utils.config_manager import ConfigManager

logger = setup_logger("Calibrator")

class Calibrator:
    def __init__(self, config_manager: ConfigManager, stream: AudioStream):
        self.config = config_manager
        self.stream = stream
        self.background_energies = []
        self.background_peaks = []
        self.clap_energies = []
        self.clap_peaks = []
        self.clap_transients = []
        self.is_collecting = False
        
    def _background_callback(self, indata: np.ndarray):
        if self.is_collecting:
            rms = FeatureExtractor.get_rms_energy(indata)
            peak = FeatureExtractor.get_peak_amplitude(indata)
            self.background_energies.append(rms)
            self.background_peaks.append(peak)
            sys.stdout.write(f"\rListening to background noise... ({len(self.background_energies)} samples)")
            sys.stdout.flush()

    def _clap_callback(self, indata: np.ndarray):
        if self.is_collecting:
            rms = FeatureExtractor.get_rms_energy(indata)
            peak = FeatureExtractor.get_peak_amplitude(indata)
            
            # Simple threshold to capture only when they clap
            if rms > np.mean(self.background_energies) * 3:
                transient = FeatureExtractor.get_transient_sharpness(indata)
                self.clap_energies.append(rms)
                self.clap_peaks.append(peak)
                self.clap_transients.append(transient)
                logger.info(f"\n[Clap recorded] Energy: {rms:.4f}, Peak: {peak:.4f}")

    def run_calibration(self):
        logger.info("Starting Calibration Mode.")
        logger.info("Please remain quiet for 5 seconds to measure background noise...")
        time.sleep(2)
        
        # 1. Background Noise Measurement
        self.is_collecting = True
        self.stream.start(self._background_callback)
        time.sleep(5)
        self.stream.stop()
        self.is_collecting = False
        
        if not self.background_energies:
            logger.error("Failed to collect background noise. Calibration aborted.")
            return
            
        bg_energy_mean = float(np.mean(self.background_energies))
        bg_peak_max = float(np.max(self.background_peaks))
        
        print()
        logger.info(f"Background Measurement Complete.")
        logger.info(f"Mean Energy: {bg_energy_mean:.5f}, Max Peak: {bg_peak_max:.5f}")
        
        # 2. Clap Measurement
        logger.info("\nNow, please clap naturally 5 times.")
        logger.info("Wait for the prompt to start clapping...")
        time.sleep(2)
        
        self.is_collecting = True
        self.stream.start(self._clap_callback)
        
        try:
            while len(self.clap_energies) < 5:
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Calibration interrupted.")
        finally:
            self.stream.stop()
            self.is_collecting = False
            
        if len(self.clap_energies) < 5:
            logger.error("Not enough claps recorded. Calibration aborted.")
            return
            
        clap_energy_min = float(np.min(self.clap_energies))
        clap_peak_min = float(np.min(self.clap_peaks))
        
        logger.info("\nClap Measurement Complete.")
        
        # 3. Calculate Thresholds
        # Set energy threshold slightly above background, but well below min clap
        suggested_energy = min((bg_energy_mean * 5), (clap_energy_min * 0.5))
        
        # Set peak threshold slightly above background peak
        suggested_peak = min((bg_peak_max * 2), (clap_peak_min * 0.5))
        
        # Confidence threshold can remain somewhat stable, but we can tune it slightly
        # For simplicity in MVP, we set it to a solid 0.6
        suggested_confidence = 0.6
        
        logger.info("\n=== Suggested Calibration Values ===")
        logger.info(f"Energy Threshold: {suggested_energy:.5f}")
        logger.info(f"Peak Threshold: {suggested_peak:.5f}")
        logger.info(f"Confidence Threshold: {suggested_confidence:.2f}")
        
        # 4. Save to Config
        self.config.set("audio", "energy_threshold", suggested_energy)
        self.config.set("audio", "peak_threshold", suggested_peak)
        self.config.set("audio", "clap_threshold", suggested_confidence)
        
        logger.info("\nCalibration values saved to config.json successfully!")
