# CLAPOS V3 — Voice-First Personal Desktop Assistant

CLAPOS V3 transforms your desktop into an intelligent, always-running, offline-first personal voice assistant. It listens via your default microphone, detects speech segments with an adaptive noise-floor Voice Activity Detector (VAD), transcribes audio with Faster-Whisper, understands spoken natural commands via a multi-layer Intent Engine, responds verbally through your laptop speakers, and automates desktop workflows asynchronously.

---

## Core Architecture

```text
                    MICROPHONE
                        │
                        ▼
              Audio Input Manager
                        │
                        ▼
             Voice Activity Detection
           (Adaptive Noise + Pre-Roll)
                        │
                        ▼
            Single-Worker STT Queue
                        │
                        ▼
             Speech-to-Text Engine
               (Faster-Whisper)
                        │
                        ▼
              Transcript Validator
                        │
                        ▼
                 Intent Engine
           (Exact -> Semantic -> Fuzzy)
                        │
                        ▼
                 Action Router
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
       Workflow      Assistant       System
       Execution      Response       Commands
          │             │
          └──────┬──────┘
                 │
                 ▼
          Text-to-Speech
             (pyttsx3)
                 │
                 ▼
              SPEAKERS
```

---

## Key Features

1. **Reliable Offline Speech Recognition**: Powered by `faster-whisper` (`base.en` default, configurable to `tiny.en` or `small.en`). Inference runs locally on CPU with int8 quantization.
2. **500ms Pre-Roll Audio Buffer**: Captures the leading syllables of speech before VAD transitions to active, preventing clipped words like *"ev mode"*.
3. **Adaptive Noise Floor VAD**: Dynamically measures ambient room and fan noise to prevent false triggers while remaining sensitive to speech.
4. **Whisper Transcript Validation**: Rejects low-confidence text, high no-speech probability frames, repetition loops, and phantom hallucination strings.
5. **3-Layer Intent Understanding**:
   - **Layer 1**: Exact normalized phrase matching.
   - **Layer 2**: Semantic key phrase matching with required semantic anchors.
   - **Layer 3**: Rapidfuzz fallback with strict tiered confidence thresholds (Conversational: `0.65`, Actions: `0.82`).
6. **Command Cooldown & Duplicate Protection**: Enforces global command cooldown (`2.0s`), duplicate intent window (`5.0s`), and unknown speech suppression (`4.0s`).
7. **Strict Self-Listening Protection Sequence**:
   ```text
   TTS Starts ──► Pause Command Acceptance ──► Flush Audio Buffers
              ──► Speak Verbal Response ──► Cooldown (300ms)
              ──► Flush Audio Buffers Again ──► Resume Command Acceptance
   ```
8. **Decoupled Workflow Execution**: Application launching runs in a dedicated background queue and does not block voice listening or speech responses.
9. **Startup Health Checks**: Automatically verifies configuration, microphone access, Faster-Whisper model loading, TTS synthesis, and workflow configurations before entering `LISTENING` state.

---

## Spoken Commands

| Spoken Phrase Examples | Intent | Verbal Response | Action |
| :--- | :--- | :--- | :--- |
| *"Dev mode"*, *"open coding setup"*, *"start coding"*, *"open vscode"* | `DEVELOPER_MODE` | *"Sure, opening your development environment."* | Launches VS Code, Antigravity, Google Chrome |
| *"Game mode"*, *"gaming mode"*, *"launch valorant"*, *"let's play"* | `GAMING_MODE` | *"Alright, switching to gaming mode."* | Launches VALORANT, Kreo Mouse Software, Google Chrome |
| *"Watch something"*, *"entertainment mode"*, *"chill out"* | `ENTERTAINMENT_MODE` | *"Okay, opening YouTube for you."* | Launches YouTube in Google Chrome |
| *"What time is it?"*, *"tell me the time"*, *"current time"* | `TIME` | *"The time is 7:30 PM."* | Speaks current system time |
| *"Hello"*, *"hey CLAPOS"*, *"good morning"* | `GREETING` | *"Hey! What can I do for you?"* | Conversational acknowledgment |
| *"What are you doing?"*, *"are you listening?"* | `STATUS` | *"I'm running and ready for your command."* | System status report |

---

## Installation & Setup

### 1. Requirements
- Windows 10/11 (x64)
- Python 3.10+
- Working microphone and laptop speakers

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run CLAPOS

To run in debug mode (recommended for real-time telemetry):
```bash
python main.py --debug
```

#### Diagnostic & Testing Modes

- **Microphone & VAD Real-Time VU Meter Test**:
  Runs a standalone VU meter without loading Whisper or workflows.
  ```bash
  python main.py --mic-test
  ```

- **List All Audio Input Devices**:
  Shows available microphones and default hardware indices.
  ```bash
  python main.py --list-devices
  ```

- **Benchmark Whisper Models (tiny.en vs base.en)**:
  Measures and compares CPU inference latency.
  ```bash
  python main.py --benchmark
  ```

Debug console output:
```text
[STARTUP] Initializing CLAPOS

[CHECK] Configuration loaded ✓
[CHECK] Microphone available ✓
[CHECK] Faster Whisper model loaded ✓
[CHECK] TTS engine initialized ✓
[CHECK] Workflow configuration loaded ✓

[ACTIVE DEVICE]
Microphone Array (Intel® Smart Sound Technology)
Input Channels: 4
Sample Rate: 16000 Hz

[VAD] Initial noise floor: 0.0040
[VAD] Current threshold: 0.0080

[INFO] Audio stream started
[INFO] VAD active
[INFO] STT worker active

[STATE] LISTENING
[VOICE] Waiting for speech...

[MIC] RMS: 0.0012 | Threshold: 0.0080 | Silence
[MIC] RMS: 0.0214 | Threshold: 0.0080 | SPEECH

[VOICE] Speech started 🎤
[VOICE] Speech ended
[VOICE] Duration: 0.74s

[STT] Processing...
[STT] Completed in 312ms

[TRANSCRIPT]
"dev mode"

[INTENT] DEVELOPER_MODE
[CONFIDENCE] 1.00

[RESPONSE] Sure, opening your development environment.

[PERFORMANCE]
Speech Duration: 0.74s
VAD Finalization Delay: 450ms
STT Latency: 312ms
Intent Latency: 2ms
Response Queue Latency: 1ms
Total Post-Speech Latency: 765ms
```

---

## Configuration (`config/config.json`)

All assistant parameters are customizable in `config/config.json`:

```json
{
  "audio": {
    "sample_rate": 16000,
    "chunk_size": 1024,
    "device": null,
    "reconnect_interval": 2.0,
    "max_reconnect_attempts": 5
  },
  "vad": {
    "adaptive_threshold": true,
    "noise_floor_window": 3.0,
    "sensitivity_multiplier": 2.5,
    "minimum_threshold": 0.008,
    "maximum_threshold": 0.08,
    "silence_duration": 1.0,
    "minimum_speech_duration": 0.4,
    "max_recording_duration": 8.0,
    "pre_roll_duration": 0.5
  },
  "voice": {
    "model": "base.en",
    "device": "cpu",
    "compute_type": "int8",
    "mode": "CONTINUOUS_COMMAND"
  },
  "transcription": {
    "min_log_probability": -1.0,
    "max_no_speech_probability": 0.6,
    "minimum_text_length": 2
  },
  "intent": {
    "conversation_threshold": 0.65,
    "action_threshold": 0.82,
    "global_cooldown": 2.0,
    "duplicate_intent_window": 5.0,
    "unknown_command_cooldown": 4.0
  },
  "tts": {
    "rate": 175,
    "volume": 1.0,
    "cooldown_duration": 0.3
  },
  "assistant": {
    "startup_greeting": true,
    "startup_message": "CLAPOS is online.",
    "completion_feedback": false
  }
}
```

---

## Persistent Background Service (PM2)

To run CLAPOS as an always-running background service on Windows:

### 1. Install PM2
```bash
npm install -g pm2
```

### 2. Start CLAPOS
```bash
pm2 start ecosystem.config.js
```

### 3. Manage Background Process
```bash
# View live logs
pm2 logs clapos

# Check status
pm2 status

# Restart or stop
pm2 restart clapos
pm2 stop clapos

# Save PM2 state across reboots
pm2 save
```

---

## Project Structure

```text
CLAPOS/
├── main.py                     # CLI Entry point with signal handling & UTF-8 console setup
├── requirements.txt            # Project dependencies
├── ecosystem.config.js         # PM2 production process configuration
├── README.md                   # Documentation
│
├── config/
│   └── config.json             # Central configuration (audio, VAD, voice, workflows)
│
├── src/
│   ├── core/
│   │   ├── assistant.py        # Central assistant orchestrator & health check
│   │   ├── event_router.py     # Intent routing, cooldowns, dynamic responses
│   │   ├── intent_engine.py    # 3-Layer semantic matching with anchors
│   │   ├── state_manager.py    # Global state transitions & speaking flags
│   │   └── command_history.py  # In-memory history ring buffer
│   │
│   ├── audio/
│   │   ├── audio_manager.py    # SoundDevice input capture & auto-reconnect
│   │   ├── audio_buffer.py     # PreRollBuffer (500ms) & SpeechAccumulator
│   │   └── voice_activity_detector.py # Adaptive noise floor VAD
│   │
│   ├── voice/
│   │   ├── speech_recognizer.py   # Faster-Whisper single worker STT
│   │   ├── transcript_validator.py# Anti-hallucination & logprob validator
│   │   ├── activation_manager.py  # Activation modes (Continuous, Wake Word, PTT)
│   │   └── tts_engine.py          # pyttsx3 worker with self-listening protection
│   │
│   ├── automation/
│   │   ├── app_launcher.py     # Process checking & Windows app launcher
│   │   └── workflow_manager.py # Async workflow worker with structured results
│   │
│   └── utils/
│       ├── config_manager.py   # Config loader & persistence
│       ├── config_validator.py # Strict config schema validation
│       └── logger.py           # Logging utility
│
└── logs/
    └── activity.log            # Assistant runtime log
```
