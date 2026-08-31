import customtkinter as ctk
from src.utils.config_manager import ConfigManager

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, config: ConfigManager, on_close_callback=None):
        super().__init__(master)
        self.title("Settings")
        self.geometry("400x500")
        self.config = config
        self.on_close_callback = on_close_callback
        
        # Make it modal
        self.transient(master)
        self.grab_set()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(self.scroll, text="Audio Settings", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        # Energy Threshold
        self.energy_var = ctk.StringVar(value=str(self.config.get("audio", "energy_threshold", 0.05)))
        ctk.CTkLabel(self.scroll, text="Energy Threshold:").pack(anchor="w")
        ctk.CTkEntry(self.scroll, textvariable=self.energy_var).pack(fill="x", pady=5)
        
        # Peak Threshold
        self.peak_var = ctk.StringVar(value=str(self.config.get("audio", "peak_threshold", 0.2)))
        ctk.CTkLabel(self.scroll, text="Peak Threshold:").pack(anchor="w")
        ctk.CTkEntry(self.scroll, textvariable=self.peak_var).pack(fill="x", pady=5)
        
        # Clap Confidence
        self.clap_var = ctk.StringVar(value=str(self.config.get("audio", "clap_threshold", 0.75)))
        ctk.CTkLabel(self.scroll, text="Confidence Threshold:").pack(anchor="w")
        ctk.CTkEntry(self.scroll, textvariable=self.clap_var).pack(fill="x", pady=5)
        
        # Save Button
        ctk.CTkButton(self.scroll, text="Save", command=self.save_settings).pack(pady=20)
        
    def save_settings(self):
        try:
            self.config.set("audio", "energy_threshold", float(self.energy_var.get()))
            self.config.set("audio", "peak_threshold", float(self.peak_var.get()))
            self.config.set("audio", "clap_threshold", float(self.clap_var.get()))
            self._on_close()
        except ValueError:
            # Simple error handling for bad inputs
            pass

    def _on_close(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.grab_release()
        self.destroy()
