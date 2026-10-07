import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import urllib.parse
import urllib.request


class BackendCheckerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Production Video Download Checker")
        self.geometry("900x650")
        self.minsize(800, 550)

        self.base_url_var = tk.StringVar(value="https://uvd-backend-production.up.railway.app")
        self.video_url_var = tk.StringVar(value="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.quality_var = tk.StringVar(value="720p")

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=14)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Backend URL (Production)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Entry(main, textvariable=self.base_url_var, width=90).pack(fill="x", pady=(4, 10))

        ttk.Label(main, text="Video URL", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Entry(main, textvariable=self.video_url_var, width=90).pack(fill="x", pady=(4, 10))

        quality_row = ttk.Frame(main)
        quality_row.pack(fill="x", pady=(0, 10))
        ttk.Label(quality_row, text="Quality", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 12))
        ttk.Combobox(
            quality_row,
            textvariable=self.quality_var,
            values=["Any", "360p", "480p", "720p", "1080p"],
            state="readonly",
            width=20,
        ).pack(side="left")

        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=(0, 12))
        ttk.Button(actions, text="Check /api/extract", command=lambda: self.call_endpoint("/api/extract")).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Check /api/download", command=lambda: self.call_endpoint("/api/download")).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Open /docs", command=self.open_docs).pack(side="left")

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main, textvariable=self.status_var, foreground="#0b5f3a", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Label(main, text="Response", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.output = scrolledtext.ScrolledText(main, wrap=tk.WORD, height=24, font=("Consolas", 10))
        self.output.pack(fill="both", expand=True)

    def _make_request(self, endpoint: str):
        base_url = self.base_url_var.get().strip().rstrip("/")
        video_url = self.video_url_var.get().strip()

        if not base_url:
            raise ValueError("Backend URL required.")
        if not video_url.startswith(("http://", "https://")):
            raise ValueError("Video URL must start with http:// or https://")

        params = {"url": video_url}
        quality = self.quality_var.get().strip()
        if quality and quality.lower() != "any":
            params["quality"] = quality

        query = urllib.parse.urlencode(params)
        request_url = f"{base_url}{endpoint}?{query}"
        request = urllib.request.Request(request_url, headers={"User-Agent": "PC-Backend-Checker/1.0", "Accept": "application/json"})
        return urllib.request.urlopen(request, timeout=90)

    def call_endpoint(self, endpoint: str):
        self.output.delete("1.0", tk.END)
        self.status_var.set(f"Calling {endpoint}...")
        try:
            with self._make_request(endpoint) as response:
                body = response.read().decode("utf-8", errors="replace")
                status = getattr(response, "status", "UNKNOWN")
                self.status_var.set(f"Success: HTTP {status}")
                try:
                    parsed = json.loads(body)
                    pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
                except json.JSONDecodeError:
                    pretty = body
                self.output.insert(tk.END, pretty)
        except Exception as exc:
            self.status_var.set("Request failed")
            error_text = f"Error: {exc}\n\nCheck if the backend is running and the URL is valid."
            self.output.insert(tk.END, error_text)
            messagebox.showerror("Backend check failed", str(exc))

    def open_docs(self):
        try:
            base_url = self.base_url_var.get().strip().rstrip("/")
            import webbrowser
            webbrowser.open(f"{base_url}/docs")
        except Exception as exc:
            messagebox.showerror("Open docs failed", str(exc))


if __name__ == "__main__":
    app = BackendCheckerApp()
    app.mainloop()
