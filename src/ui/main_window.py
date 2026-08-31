import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw
import threading
import os
import time
from src.ui.dashboard import DashboardFrame
from src.ui.settings_window import SettingsWindow
from src.utils.config_manager import ConfigManager

class MainWindow(ctk.CTk):
    def __init__(self, config: ConfigManager, start_audio_cb, stop_audio_cb):
        super().__init__()
        
        self.config = config
        self.start_audio = start_audio_cb
        self.stop_audio = stop_audio_cb
        self.is_listening = True
        
        self.title("CLAPOS")
        self.geometry("500x600")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Prevent default closing behavior (minimize to tray instead)
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        
        self.dashboard = DashboardFrame(self)
        self.dashboard.pack(fill="both", expand=True)
        
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.pack(fill="x", padx=20, pady=20)
        
        self.toggle_btn = ctk.CTkButton(self.controls_frame, text="Pause Listening", command=self.toggle_listening)
        self.toggle_btn.pack(side="left", padx=10, expand=True)
        
        self.settings_btn = ctk.CTkButton(self.controls_frame, text="Settings", command=self.open_settings)
        self.settings_btn.pack(side="right", padx=10, expand=True)
        
        self.settings_window = None
        self.tray_icon = None
        self.icon_image = self._create_placeholder_icon()
        
    def _create_placeholder_icon(self):
        """Creates a simple placeholder icon for the system tray."""
        image = Image.new('RGB', (64, 64), color=(46, 204, 113))
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 16, 48, 48), fill=(255, 255, 255))
        return image
        
    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.toggle_btn.configure(text="Pause Listening")
            self.dashboard.set_status(True)
            self.start_audio()
        else:
            self.toggle_btn.configure(text="Resume Listening")
            self.dashboard.set_status(False)
            self.stop_audio()
            
    def open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self, self.config)
        else:
            self.settings_window.focus()
            
    def minimize_to_tray(self):
        self.withdraw() # Hide window
        
        menu = pystray.Menu(
            pystray.MenuItem('Open CLAPOS', self.show_window),
            pystray.MenuItem('Exit', self.quit_app)
        )
        self.tray_icon = pystray.Icon("CLAPOS", self.icon_image, "CLAPOS - Active", menu)
        
        # Run tray in a separate thread to not block
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.after(0, self.deiconify)
        
    def quit_app(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.stop_audio()
        self.quit()
        
    def update_dashboard(self, mic_level, confidence, sequence, last_action):
        # Must be called thread-safe if updated from audio callback
        self.after(0, lambda: self.dashboard.update_metrics(mic_level, confidence, sequence, last_action))
