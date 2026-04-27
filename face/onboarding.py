"""First-run onboarding wizard for OnyxKraken."""

import logging
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.license import activate_license, generate_key, get_license_type

_log = logging.getLogger("onboarding")


class OnboardingWizard:
    """First-run setup wizard."""
    
    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Welcome to OnyxKraken")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # State
        self.current_step = 0
        self.steps = [
            self._step_welcome,
            self._step_ollama_check,
            self._step_license,
            self._step_complete,
        ]
        
        # UI
        self.content_frame = tk.Frame(self.root, bg="#1a1a2e", padx=40, pady=30)
        self.content_frame.pack(fill="both", expand=True)
        
        self.button_frame = tk.Frame(self.root, bg="#16213e", pady=15)
        self.button_frame.pack(fill="x", side="bottom")
        
        self.back_btn = tk.Button(
            self.button_frame, text="← Back", command=self._prev_step,
            bg="#0f3460", fg="#e94560", font=("Segoe UI", 10, "bold"),
            padx=20, pady=8, relief="flat", cursor="hand2"
        )
        self.back_btn.pack(side="left", padx=20)
        
        self.next_btn = tk.Button(
            self.button_frame, text="Next →", command=self._next_step,
            bg="#e94560", fg="white", font=("Segoe UI", 10, "bold"),
            padx=20, pady=8, relief="flat", cursor="hand2"
        )
        self.next_btn.pack(side="right", padx=20)
        
        # Show first step
        self._show_step()
    
    def _clear_content(self):
        """Clear the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def _show_step(self):
        """Show the current step."""
        self._clear_content()
        
        # Update buttons
        self.back_btn.config(state="normal" if self.current_step > 0 else "disabled")
        
        if self.current_step == len(self.steps) - 1:
            self.next_btn.config(text="Finish")
        else:
            self.next_btn.config(text="Next →")
        
        # Show step content
        self.steps[self.current_step]()
    
    def _next_step(self):
        """Go to next step."""
        if self.current_step == len(self.steps) - 1:
            # Finish
            self.root.destroy()
        else:
            self.current_step += 1
            self._show_step()
    
    def _prev_step(self):
        """Go to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._show_step()
    
    def _step_welcome(self):
        """Welcome step."""
        tk.Label(
            self.content_frame, text="Welcome to OnyxKraken! 👋",
            bg="#1a1a2e", fg="#e94560", font=("Segoe UI", 24, "bold")
        ).pack(pady=(0, 20))
        
        tk.Label(
            self.content_frame,
            text="A local AI agent with a face.\n\n"
                 "I see your screen, control your computer,\n"
                 "learn from every task, and build 3D worlds.\n\n"
                 "100% local. No cloud. No subscription.",
            bg="#1a1a2e", fg="#ffffff", font=("Segoe UI", 12),
            justify="center"
        ).pack(pady=20)
        
        tk.Label(
            self.content_frame,
            text="Let's get you set up in 3 quick steps.",
            bg="#1a1a2e", fg="#aaaaaa", font=("Segoe UI", 10, "italic")
        ).pack(pady=20)
    
    def _step_ollama_check(self):
        """Check if Ollama is installed and running."""
        tk.Label(
            self.content_frame, text="Step 1: Ollama Setup",
            bg="#1a1a2e", fg="#e94560", font=("Segoe UI", 18, "bold")
        ).pack(pady=(0, 20))
        
        tk.Label(
            self.content_frame,
            text="OnyxKraken requires Ollama to run local AI models.",
            bg="#1a1a2e", fg="#ffffff", font=("Segoe UI", 11)
        ).pack(pady=10)
        
        # Check if Ollama is installed
        ollama_installed = self._check_ollama_installed()
        ollama_running = self._check_ollama_running()
        
        status_frame = tk.Frame(self.content_frame, bg="#1a1a2e")
        status_frame.pack(pady=20)
        
        if ollama_installed:
            tk.Label(
                status_frame, text="✅ Ollama is installed",
                bg="#1a1a2e", fg="#00ff00", font=("Segoe UI", 11)
            ).pack(anchor="w")
        else:
            tk.Label(
                status_frame, text="❌ Ollama not found",
                bg="#1a1a2e", fg="#ff0000", font=("Segoe UI", 11)
            ).pack(anchor="w")
        
        if ollama_running:
            tk.Label(
                status_frame, text="✅ Ollama is running",
                bg="#1a1a2e", fg="#00ff00", font=("Segoe UI", 11)
            ).pack(anchor="w")
        else:
            tk.Label(
                status_frame, text="❌ Ollama is not running",
                bg="#1a1a2e", fg="#ff0000", font=("Segoe UI", 11)
            ).pack(anchor="w")
        
        if not ollama_installed or not ollama_running:
            tk.Label(
                self.content_frame,
                text="\nPlease install Ollama from:\nhttps://ollama.com\n\n"
                     "Then run these commands:\n"
                     "ollama pull llama3.2-vision\n"
                     "ollama pull deepseek-r1:14b",
                bg="#1a1a2e", fg="#ffaa00", font=("Consolas", 10),
                justify="left"
            ).pack(pady=10)
    
    def _check_ollama_installed(self) -> bool:
        """Check if Ollama is installed."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _check_ollama_running(self) -> bool:
        """Check if Ollama is running."""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def _step_license(self):
        """License activation step."""
        tk.Label(
            self.content_frame, text="Step 2: License Activation",
            bg="#1a1a2e", fg="#e94560", font=("Segoe UI", 18, "bold")
        ).pack(pady=(0, 20))
        
        license_type = get_license_type()
        
        if license_type == "full":
            tk.Label(
                self.content_frame,
                text="✅ Full license activated!",
                bg="#1a1a2e", fg="#00ff00", font=("Segoe UI", 14, "bold")
            ).pack(pady=20)
            
            tk.Label(
                self.content_frame,
                text="You have access to all features.",
                bg="#1a1a2e", fg="#ffffff", font=("Segoe UI", 11)
            ).pack()
        else:
            tk.Label(
                self.content_frame,
                text="You're running in Demo Mode",
                bg="#1a1a2e", fg="#ffaa00", font=("Segoe UI", 12)
            ).pack(pady=10)
            
            tk.Label(
                self.content_frame,
                text="Demo limits:\n"
                     "• 3 automation tasks per session\n"
                     "• ToolForge, Voice, Recording disabled\n"
                     "• Self-improvement disabled",
                bg="#1a1a2e", fg="#aaaaaa", font=("Segoe UI", 10),
                justify="left"
            ).pack(pady=10)
            
            tk.Label(
                self.content_frame,
                text="\nTo unlock full features, enter your license key:",
                bg="#1a1a2e", fg="#ffffff", font=("Segoe UI", 10)
            ).pack(pady=10)
            
            key_frame = tk.Frame(self.content_frame, bg="#1a1a2e")
            key_frame.pack(pady=10)
            
            self.key_entry = tk.Entry(
                key_frame, width=40, font=("Consolas", 11),
                bg="#16213e", fg="#ffffff", insertbackground="#ffffff"
            )
            self.key_entry.pack(side="left", padx=5)
            
            activate_btn = tk.Button(
                key_frame, text="Activate", command=self._activate_license,
                bg="#e94560", fg="white", font=("Segoe UI", 10, "bold"),
                padx=15, pady=5, relief="flat", cursor="hand2"
            )
            activate_btn.pack(side="left")
            
            tk.Label(
                self.content_frame,
                text="\nDon't have a license? Get one at:\nhttps://onyxkraken.com",
                bg="#1a1a2e", fg="#aaaaaa", font=("Segoe UI", 9),
                justify="center"
            ).pack(pady=10)
    
    def _activate_license(self):
        """Activate the entered license key."""
        key = self.key_entry.get().strip()
        
        if activate_license(key):
            messagebox.showinfo("Success", "License activated successfully!")
            self._show_step()  # Refresh
        else:
            messagebox.showerror("Error", "Invalid license key")
    
    def _step_complete(self):
        """Completion step."""
        tk.Label(
            self.content_frame, text="You're All Set! 🎉",
            bg="#1a1a2e", fg="#e94560", font=("Segoe UI", 24, "bold")
        ).pack(pady=(0, 20))
        
        tk.Label(
            self.content_frame,
            text="OnyxKraken is ready to use.\n\n"
                 "Try saying:\n"
                 "• 'Open Notepad and type Hello World'\n"
                 "• 'Create a 3D character in Blender'\n"
                 "• 'Build me a calculator app'\n\n"
                 "I'll see your screen, plan the steps,\n"
                 "and execute them autonomously.",
            bg="#1a1a2e", fg="#ffffff", font=("Segoe UI", 11),
            justify="center"
        ).pack(pady=20)
        
        tk.Label(
            self.content_frame,
            text="Click Finish to start!",
            bg="#1a1a2e", fg="#aaaaaa", font=("Segoe UI", 10, "italic")
        ).pack(pady=20)
    
    def run(self):
        """Run the wizard."""
        self.root.mainloop()


def should_show_onboarding() -> bool:
    """Check if onboarding should be shown (first run)."""
    marker_file = Path.home() / ".onyxkraken" / "onboarding_complete"
    return not marker_file.exists()


def mark_onboarding_complete():
    """Mark onboarding as complete."""
    marker_file = Path.home() / ".onyxkraken" / "onboarding_complete"
    marker_file.parent.mkdir(parents=True, exist_ok=True)
    marker_file.touch()


if __name__ == "__main__":
    wizard = OnboardingWizard()
    wizard.run()
