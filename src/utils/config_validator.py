from typing import Dict, Any, List
from src.utils.logger import setup_logger

logger = setup_logger("ConfigValidator")

class ConfigValidationError(Exception):
    pass

class ConfigValidator:
    @staticmethod
    def validate(config: Dict[str, Any]) -> bool:
        """
        Validates the configuration dictionary against expected types and ranges.
        Raises ConfigValidationError with actionable messages if invalid.
        """
        errors: List[str] = []

        # Audio section
        audio = config.get("audio", {})
        if not isinstance(audio, dict):
            errors.append("'audio' section must be a dictionary.")
        else:
            sr = audio.get("sample_rate")
            if not isinstance(sr, int) or sr <= 0:
                errors.append("audio.sample_rate must be a positive integer (e.g. 16000).")
            cs = audio.get("chunk_size")
            if not isinstance(cs, int) or cs <= 0:
                errors.append("audio.chunk_size must be a positive integer (e.g. 1024).")

        # VAD section
        vad = config.get("vad", {})
        if not isinstance(vad, dict):
            errors.append("'vad' section must be a dictionary.")
        else:
            min_th = vad.get("minimum_threshold", 0.008)
            max_th = vad.get("maximum_threshold", 0.08)
            if not (0 < min_th < max_th):
                errors.append(f"vad thresholds invalid: minimum_threshold ({min_th}) must be < maximum_threshold ({max_th}) and > 0.")
            
            silence_d = vad.get("silence_duration")
            if not isinstance(silence_d, (int, float)) or silence_d <= 0:
                errors.append("vad.silence_duration must be a positive number.")
                
            min_speech_d = vad.get("minimum_speech_duration")
            if not isinstance(min_speech_d, (int, float)) or min_speech_d <= 0:
                errors.append("vad.minimum_speech_duration must be a positive number.")
                
            max_rec_d = vad.get("max_recording_duration")
            if not isinstance(max_rec_d, (int, float)) or max_rec_d <= (min_speech_d or 0):
                errors.append("vad.max_recording_duration must be greater than minimum_speech_duration.")

            pre_roll_d = vad.get("pre_roll_duration", 0.5)
            if not isinstance(pre_roll_d, (int, float)) or pre_roll_d < 0:
                errors.append("vad.pre_roll_duration must be a non-negative number.")

        # Voice section
        voice = config.get("voice", {})
        if not isinstance(voice, dict):
            errors.append("'voice' section must be a dictionary.")
        else:
            model = voice.get("model")
            if not isinstance(model, str) or not model.strip():
                errors.append("voice.model must be a non-empty string (e.g. 'base.en').")

        # Transcription section
        transcription = config.get("transcription", {})
        if not isinstance(transcription, dict):
            errors.append("'transcription' section must be a dictionary.")
        else:
            min_len = transcription.get("minimum_text_length", 2)
            if not isinstance(min_len, int) or min_len < 1:
                errors.append("transcription.minimum_text_length must be an integer >= 1.")

        # Intent section
        intent = config.get("intent", {})
        if not isinstance(intent, dict):
            errors.append("'intent' section must be a dictionary.")
        else:
            conv_th = intent.get("conversation_threshold", 0.65)
            action_th = intent.get("action_threshold", 0.82)
            if not (0.0 <= conv_th <= 1.0):
                errors.append("intent.conversation_threshold must be between 0.0 and 1.0.")
            if not (0.0 <= action_th <= 1.0):
                errors.append("intent.action_threshold must be between 0.0 and 1.0.")

        # Workflows section
        workflows = config.get("workflows", {})
        if not isinstance(workflows, dict):
            errors.append("'workflows' section must be a dictionary.")
        else:
            for wf_id, wf_data in workflows.items():
                if not isinstance(wf_data, dict):
                    errors.append(f"workflow '{wf_id}' must be a dictionary.")
                    continue
                apps = wf_data.get("apps", [])
                if not isinstance(apps, list):
                    errors.append(f"workflow '{wf_id}.apps' must be a list.")

        # Automation section (optional)
        automation = config.get("automation", {})
        if automation and not isinstance(automation, dict):
            errors.append("'automation' section must be a dictionary.")

        if errors:
            msg = "\n[CONFIG ERROR] " + "\n[CONFIG ERROR] ".join(errors)
            logger.error(msg)
            raise ConfigValidationError(msg)

        return True
