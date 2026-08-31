import numpy as np
import speech_recognition as sr
import threading
import time
from typing import Callable, Optional
from src.utils.logger import setup_logger

logger = setup_logger("SpeechDetector")

class SpeechDetector:
    def __init__(self, 
                 sample_rate: int = 44100, 
                 energy_threshold: float = 0.05,
                 silence_timeout: float = 1.0,
                 debug: bool = False):
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.silence_timeout = silence_timeout
        self.debug = debug
        
        self.recognizer = sr.Recognizer()
        
        # Audio accumulation buffer
        self.buffer = []
        self.is_speaking = False
        self.last_speech_time = time.time()
        
        # Callback for when speech is recognized
        self.on_speech_recognized: Optional[Callable[[str], None]] = None
        
        # Lock to prevent concurrent API calls
        self.is_processing = False

    def set_callback(self, callback: Callable[[str], None]):
        self.on_speech_recognized = callback

    def _get_rms(self, audio_data: np.ndarray) -> float:
        return float(np.sqrt(np.mean(audio_data**2)))

    def analyze_chunk(self, audio_data: np.ndarray):
        """Processes an incoming chunk of audio from sounddevice."""
        rms = self._get_rms(audio_data)
        current_time = time.time()
        
        if rms > self.energy_threshold:
            # Active speech
            if not self.is_speaking:
                if self.debug:
                    logger.debug("Speech started...")
                self.is_speaking = True
                self.buffer = [] # Clear buffer on new speech
                
            self.last_speech_time = current_time
            self.buffer.append(audio_data)
        else:
            # Silence
            if self.is_speaking:
                self.buffer.append(audio_data) # Keep adding trailing silence
                
                if current_time - self.last_speech_time > self.silence_timeout:
                    # Silence timeout reached, process speech
                    if self.debug:
                        logger.debug("Speech ended, processing...")
                    self.is_speaking = False
                    self._process_buffer_async()

    def _process_buffer_async(self):
        if self.is_processing or not self.buffer:
            return
            
        # Copy the buffer
        audio_chunks = list(self.buffer)
        self.buffer = []
        
        thread = threading.Thread(target=self._recognize_speech, args=(audio_chunks,), daemon=True)
        thread.start()

    def _recognize_speech(self, audio_chunks):
        self.is_processing = True
        try:
            # Concatenate all numpy array chunks
            full_audio = np.concatenate(audio_chunks)
            
            # Ensure it's 16-bit PCM for SpeechRecognition
            # sounddevice typically provides float32 [-1.0, 1.0] by default in our app
            # Convert float32 to int16
            audio_int16 = (full_audio * 32767).astype(np.int16)
            
            # Convert to raw bytes
            raw_audio = audio_int16.tobytes()
            
            # Create AudioData object (sample width is 2 bytes for int16)
            audio_data = sr.AudioData(raw_audio, self.sample_rate, 2)
            
            if self.debug:
                logger.debug("Sending to Google Speech Recognition...")
                
            # Call Google API
            text = self.recognizer.recognize_google(audio_data)
            
            logger.info(f"[SPEECH] Recognized: '{text}'")
            
            if self.on_speech_recognized:
                self.on_speech_recognized(text.lower())
                
        except sr.UnknownValueError:
            if self.debug:
                logger.debug("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            logger.error(f"Could not request results from Google Speech Recognition service; {e}")
        except Exception as e:
            logger.error(f"Error during speech recognition: {e}")
        finally:
            self.is_processing = False
