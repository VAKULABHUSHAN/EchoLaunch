import customtkinter as ctk

class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Header
        self.header = ctk.CTkLabel(self, text="CLAPOS", font=ctk.CTkFont(size=32, weight="bold"))
        self.header.pack(pady=(20, 5))
        
        self.subtitle = ctk.CTkLabel(self, text="Acoustic Gesture Desktop Automation", text_color="gray")
        self.subtitle.pack(pady=(0, 20))
        
        # Status Card
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(fill="x", padx=20, pady=10)
        
        self.status_indicator = ctk.CTkLabel(self.status_frame, text="🟢 LISTENING", font=ctk.CTkFont(size=18, weight="bold"), text_color="#2ecc71")
        self.status_indicator.pack()
        
        # Metrics Card
        self.metrics_frame = ctk.CTkFrame(self)
        self.metrics_frame.pack(fill="x", padx=20, pady=10)
        
        self.level_label = ctk.CTkLabel(self.metrics_frame, text="Mic Level: 0.00")
        self.level_label.pack(pady=5)
        
        self.seq_label = ctk.CTkLabel(self.metrics_frame, text="Phrase: Waiting...")
        self.seq_label.pack(pady=5)
        
        # Workflow Info
        self.workflow_label = ctk.CTkLabel(self, text="Last Action: None", font=ctk.CTkFont(size=14, slant="italic"), text_color="gray")
        self.workflow_label.pack(pady=20)
        
    def update_metrics(self, mic_level: float, confidence: float, sequence: str, last_action: str):
        self.level_label.configure(text=f"Mic Level: {mic_level:.4f}")
        self.seq_label.configure(text=f"Phrase: {sequence}")
        if last_action:
            self.workflow_label.configure(text=f"Last Action: {last_action}")
            
    def set_status(self, is_listening: bool):
        if is_listening:
            self.status_indicator.configure(text="🟢 LISTENING", text_color="#2ecc71")
        else:
            self.status_indicator.configure(text="🔴 PAUSED", text_color="#e74c3c")
