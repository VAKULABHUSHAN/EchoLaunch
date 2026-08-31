# CLAPOS — Acoustic Gesture Desktop Automation

CLAPOS is a lightweight, real-time acoustic gesture desktop assistant. It continuously listens for intentional clap sequences (e.g., double clap, triple clap) and uses them to trigger customizable desktop workflows.

## Installation & Dependencies

CLAPOS is built for Python 3.11+.

1. Clone or download this repository.
2. Ensure you have a working microphone.
3. Install the dependencies:

```bash
pip install -r requirements.txt
```

**Required Libraries:**
- `sounddevice` (Microphone stream)
- `numpy` & `scipy` (Signal processing)
- `psutil` & `pywin32` (Process management)
- `customtkinter` (Modern UI)
- `pystray` & `Pillow` (System tray integration)

## Running the Application

To run the application with the full GUI:
```bash
python main.py
```

### CLI Modes

- **Calibration Mode**: Automatically measures background noise and claps to suggest optimal thresholds for your microphone.
  ```bash
  python main.py --calibrate
  ```
- **Debug Mode**: Prints detailed audio feature extraction scores to the console (useful for tuning thresholds).
  ```bash
  python main.py --debug
  ```

## Configuration & Workflows

Configuration is stored in `config/config.json`.

### Adding New Workflows
To add a new workflow, map a clap count to an action in the `commands` section of `config.json`.
For example, to map 4 claps to launch Notepad:

```json
"commands": {
    "4": {
        "name": "Note Mode",
        "apps": [
            {
                "name": "Notepad",
                "path": "notepad.exe"
            }
        ]
    }
}
```

*Note: You can specify absolute paths (e.g., `C:\\Program Files\\...`) or system commands (e.g., `chrome.exe`) in the `path` field.*

## Adjusting Clap Sensitivity

If CLAPOS is too sensitive or not sensitive enough, you can adjust the thresholds via the **Settings** menu in the GUI or manually edit `config.json`.

- **Energy Threshold**: The minimum RMS energy required to even consider a sound as a clap.
- **Peak Threshold**: The minimum peak amplitude required.
- **Confidence Threshold (0.0 to 1.0)**: The strictness of the clap shape detection. A higher value (e.g., 0.85) requires a very sharp, clear clap. A lower value (e.g., 0.50) is more lenient but prone to false positives.

### Troubleshooting False Positives

If keyboard typing or speech is triggering CLAPOS:
1. **Run the Calibration Tool**: `python main.py --calibrate` will measure your ambient environment.
2. **Increase the Confidence Threshold**: Change it to `0.80` or `0.85` in Settings.
3. **Check Debug Mode**: Run `python main.py --debug` and look at the scores when you type vs when you clap. You will see that claps have higher `Transient Scores` and `ZCR Scores`. Adjust thresholds accordingly.

## Microphone Setup

CLAPOS uses your system's default recording device.
To change it, set your desired microphone as the "Default Input Device" in the Windows Sound Settings before starting CLAPOS.

---
*Built with ❤️ and CustomTkinter.*
