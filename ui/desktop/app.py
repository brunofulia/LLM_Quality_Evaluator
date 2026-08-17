import os
import sys
import json
import threading
from pathlib import Path
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
import yaml

# Add the root directory to sys.path so we can import 'engine'
if getattr(sys, 'frozen', False):
    project_root = Path(sys._MEIPASS)
else:
    project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from engine.config.project_config import ProjectConfig
from engine.discovery.model_fetcher import ModelFetcher
from engine.profiles.loader import ProfileLoader, MetricConfig
from engine.evaluation.adapters.deepeval_adapter import DeepEvalAdapter
from engine.evaluation.evaluator import EvaluatorEngine
from engine.exporters.html_reporter import HTMLReporter
from engine.exporters.excel_reporter import ExcelReporter

# Configuración básica de CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ENV_FILE = project_root / ".env"

CUSTOM_METRICS_DIR = project_root / "engine" / "profiles" / "custom_metrics"
os.makedirs(CUSTOM_METRICS_DIR, exist_ok=True)

def get_env_var_name(provider: str) -> str:
    mapping = {
        "openai": "OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
        "mock": "MOCK"
    }
    return mapping.get(provider.lower(), "")

def load_api_key(provider="openai"):
    env_var = get_env_var_name(provider)
    if not env_var: return ""
    
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.startswith(env_var + "="):
                    return line.strip().split("=", 1)[1]
    return ""

def save_api_key(provider, key: str):
    env_var = get_env_var_name(provider)
    if not env_var: return
    
    lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()
            
    with open(ENV_FILE, "w") as f:
        found = False
        for line in lines:
            if line.startswith(env_var + "="):
                f.write(f"{env_var}={key}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"{env_var}={key}\n")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("LLM Quality Evaluator - Unified Workbench")
        self.geometry("1100x700")
        
        # Grid layout principal: 1 fila, 2 columnas (Sidebar y Main Area)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0) # Sidebar fijo
        self.grid_columnconfigure(1, weight=1) # Main Area expandible
        
        # --- Variables globales ---
        self.provider_var = ctk.StringVar(value="Select provider...")
        self.api_key_var = tk.StringVar()
        self.model_var = ctk.StringVar(value="")
        self.profile_path_var = tk.StringVar()
        
        # Variables para batch
        self.proj_name_var = tk.StringVar()
        self.dataset_path_var = tk.StringVar()
        self.outdir_path_var = tk.StringVar()
        
        # Configurar UI
        self.setup_sidebar()
        self.setup_main_area()
        
    def setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(11, weight=1)
        
        ctk.CTkLabel(self.sidebar_frame, text="Global Configuration", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Provider
        ctk.CTkLabel(self.sidebar_frame, text="Provider:", anchor="w").grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.opt_provider = ctk.CTkOptionMenu(self.sidebar_frame, variable=self.provider_var, 
                                              values=["google", "openai", "groq", "anthropic", "mock"],
                                              command=self.on_provider_change)
        self.opt_provider.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="ew")
        
        # API Key
        ctk.CTkLabel(self.sidebar_frame, text="API Key:", anchor="w").grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")
        self.entry_api = ctk.CTkEntry(self.sidebar_frame, textvariable=self.api_key_var, show="*", state="disabled")
        self.entry_api.grid(row=4, column=0, padx=20, pady=(5, 5), sticky="ew")
        
        btn_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.btn_save_api = ctk.CTkButton(btn_frame, text="Validate", command=self.on_save_api, state="disabled")
        self.btn_save_api.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.btn_delete_api = ctk.CTkButton(btn_frame, text="Delete", command=self.on_delete_api, state="disabled", fg_color="#d9534f", hover_color="#c9302c")
        self.btn_delete_api.pack(side="right", expand=True, fill="x", padx=(5, 0))
        
        # Modelo
        ctk.CTkLabel(self.sidebar_frame, text="Model to use:", anchor="w").grid(row=6, column=0, padx=20, pady=(10, 0), sticky="w")
        self.opt_model = ctk.CTkOptionMenu(self.sidebar_frame, variable=self.model_var, values=["Waiting for provider..."])
        self.opt_model.configure(state="disabled")
        self.opt_model.grid(row=7, column=0, padx=20, pady=(5, 10), sticky="ew")
        
        # Política YAML
        ctk.CTkLabel(self.sidebar_frame, text="YAML Policy:", anchor="w").grid(row=8, column=0, padx=20, pady=(10, 0), sticky="w")
        self.entry_policy = ctk.CTkEntry(self.sidebar_frame, textvariable=self.profile_path_var, state="disabled")
        self.entry_policy.grid(row=9, column=0, padx=20, pady=(5, 5), sticky="ew")
        
        pol_btn_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        pol_btn_frame.grid(row=10, column=0, padx=20, pady=(0, 20), sticky="ew")
        ctk.CTkButton(pol_btn_frame, text="Browse", command=self.select_profile).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkButton(pol_btn_frame, text="Interactive", command=self.open_interactive_policy_dialog, fg_color="#5cb85c", hover_color="#4cae4c").pack(side="right", expand=True, fill="x", padx=(5, 0))

    def setup_main_area(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.tab_manual = self.tabview.add("1. Manual Sandbox")
        self.tab_batch = self.tabview.add("2. Batch Audit")
        self.tab_geval = self.tabview.add("3. GEval Designer")
        
        self.setup_manual_tab()
        self.setup_batch_tab()
        self.setup_geval_tab()

    def setup_manual_tab(self):
        self.tab_manual.grid_rowconfigure(2, weight=1)
        self.tab_manual.grid_columnconfigure(0, weight=1)
        self.tab_manual.grid_columnconfigure(1, weight=1)
        
        # --- INPUT (Prompt) ---
        lbl_input = ctk.CTkLabel(self.tab_manual, text="Input (Prompt):", font=("Arial", 12, "bold"))
        lbl_input.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
        
        self.txt_input = ctk.CTkTextbox(self.tab_manual, height=150)
        self.txt_input.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        # --- ACTUAL OUTPUT (Respuesta) ---
        lbl_output = ctk.CTkLabel(self.tab_manual, text="Actual Output (Output to evaluate):", font=("Arial", 12, "bold"))
        lbl_output.grid(row=0, column=1, padx=10, pady=(10, 0), sticky="w")
        
        self.txt_output = ctk.CTkTextbox(self.tab_manual, height=150)
        self.txt_output.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        # --- BOTÓN EVALUAR ---
        self.btn_eval_manual = ctk.CTkButton(self.tab_manual, text="Evaluate Case Manually", 
                                             command=self.on_eval_manual, height=40, font=("Arial", 14, "bold"))
        self.btn_eval_manual.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
        
        # --- RESULTADOS ---
        lbl_res = ctk.CTkLabel(self.tab_manual, text="Evaluation Results:", font=("Arial", 12, "bold"))
        lbl_res.grid(row=3, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="w")
        
        self.txt_results = ctk.CTkTextbox(self.tab_manual, state="disabled")
        self.txt_results.grid(row=4, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="nsew")
        self.tab_manual.grid_rowconfigure(4, weight=1)

    def setup_batch_tab(self):
        # Frame de config batch
        frame_batch_conf = ctk.CTkFrame(self.tab_batch, border_width=1, border_color="#444444")
        frame_batch_conf.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame_batch_conf, text="Project Configuration", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(10,0))
        
        self.create_file_row(frame_batch_conf, "Project Name:", self.proj_name_var, None, is_entry=True)
        self.create_file_row(frame_batch_conf, "Dataset (CSV/XLSX):", self.dataset_path_var, self.select_dataset)
        self.create_file_row(frame_batch_conf, "Output Folder:", self.outdir_path_var, self.select_outdir)
        
        btn_frame = ctk.CTkFrame(self.tab_batch, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        btn_save_proj = ctk.CTkButton(btn_frame, text="Save project.json", command=self.on_save_project, height=35)
        btn_save_proj.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        self.btn_run_batch = ctk.CTkButton(btn_frame, text="▶ Start Batch Audit", command=self.on_run_batch, height=35, fg_color="#f0ad4e", hover_color="#ec971f")
        self.btn_run_batch.pack(side="right", expand=True, fill="x", padx=(5, 0))
        
        # Consola / Logs
        ctk.CTkLabel(self.tab_batch, text="Execution Logs:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.txt_batch_logs = ctk.CTkTextbox(self.tab_batch, state="disabled")
        self.txt_batch_logs.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        self.txt_batch_logs.tag_config("info_tag", foreground="#5bc0de")
        self.txt_batch_logs.tag_config("yellow_tag", foreground="#f0ad4e")
        self.txt_batch_logs.tag_config("ok_tag", foreground="#5cb85c")
        self.txt_batch_logs.tag_config("warning_tag", foreground="#f0ad4e")
        self.txt_batch_logs.tag_config("error_tag", foreground="#d9534f")

    def create_file_row(self, parent, label_text, str_var, command, is_entry=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row, text=label_text, width=150, anchor="w").pack(side="left")
        
        if is_entry:
            ctk.CTkEntry(row, textvariable=str_var, width=300).pack(side="left", padx=(0,10))
        else:
            ctk.CTkEntry(row, textvariable=str_var, width=300, state="disabled").pack(side="left", padx=(0,10))
            if command:
                ctk.CTkButton(row, text="Browse...", command=command, width=100).pack(side="left")

    # --- SIDEBAR LOGIC ---
    def on_provider_change(self, selected_provider):
        if selected_provider == "Select provider...":
            self.entry_api.configure(state="disabled")
            self.btn_save_api.configure(state="disabled")
            self.btn_delete_api.configure(state="disabled")
            self.opt_model.configure(state="disabled")
            return
            
        self.entry_api.configure(state="normal")
        self.btn_save_api.configure(state="normal")
        self.btn_delete_api.configure(state="normal")
        
        new_key = load_api_key(selected_provider)
        self.api_key_var.set(new_key)
        self.opt_model.configure(state="disabled")
        
        if new_key:
            self.model_var.set("Loading models...")
            self.fetch_models_async(selected_provider, new_key)
        else:
            self.model_var.set("Enter your API Key")

    def on_save_api(self):
        key = self.api_key_var.get().strip()
        provider = self.provider_var.get()
        if key:
            save_api_key(provider, key)
            env_var = get_env_var_name(provider)
            if env_var:
                os.environ[env_var] = key
                
            self.model_var.set("Loading models...")
            self.fetch_models_async(provider, key)
        else:
            messagebox.showerror("Error", "The key cannot be empty.")

    def on_delete_api(self):
        provider = self.provider_var.get()
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete the saved key for {provider}?"):
            save_api_key(provider, "")
            self.api_key_var.set("")
            self.model_var.set("Enter your API Key")
            self.opt_model.configure(values=["Waiting for credentials..."], state="disabled")

    def fetch_models_async(self, provider, key):
        def fetch_task():
            try:
                models = ModelFetcher.fetch_models(provider, key)
                self.after(0, self.update_models, models, None)
            except ValueError as e:
                self.after(0, self.update_models, [], str(e))
            except Exception as e:
                self.after(0, self.update_models, [], "Connection Error")
            
        threading.Thread(target=fetch_task, daemon=True).start()
        
    def update_models(self, models, error):
        self.opt_model.configure(state="normal")
        if models:
            self.opt_model.configure(values=models)
            self.model_var.set(models[0])
        else:
            err_msg = error if error else "No models found"
            self.opt_model.configure(values=[err_msg])
            self.model_var.set(err_msg)
            if error:
                messagebox.showerror("Validation Error", err_msg)

    def select_profile(self):
        path = filedialog.askopenfilename(title="Select YAML Policy", filetypes=[("YAML Files", "*.yaml *.yml")])
        if path:
            self.profile_path_var.set(path)

    def open_interactive_policy_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Crear Política Interactive")
        dialog.geometry("450x550")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Select metrics and thresholds:", font=("Arial", 14, "bold")).pack(pady=(15, 5))
        
        # General help about Threshold
        help_text = ("💡 Threshold: The minimum score (0.0 to 1.0)\n"
                     "that the answer must reach to pass the metric.")
        ctk.CTkLabel(dialog, text=help_text, text_color="gray", font=("Arial", 12)).pack(pady=(0, 15))
        
        # Metrics dictionary with descriptions for the help button
        metrics_info = {
            "AnswerRelevancy": "Measures if the answer directly addresses the question without adding irrelevant information.\n\n⚠️ Threshold: A HIGHER value (e.g. 0.8) is STRICTER. It demands greater relevance to pass.",
            "Toxicity": "Detects offensive, discriminatory or harmful language in the generated response.\n\n⚠️ Threshold: A LOWER value (e.g. 0.1) is STRICTER. It will tolerate less toxicity before failing.",
            "Bias": "Evaluates if the text contains evident biases (gender, race, politics, etc).\n\n⚠️ Threshold: A LOWER value (e.g. 0.1) is STRICTER. It will tolerate less bias.",
            "Hallucination": "Checks if the model is inventing facts that contradict the real context.\n\n⚠️ Threshold: A LOWER value (e.g. 0.1) is STRICTER. It will tolerate less hallucinations.",
            "Summarization": "Evaluates if a summary captures the key points of the original text without omitting critical data.\n\n⚠️ Threshold: A HIGHER value (e.g. 0.8) is STRICTER. It demands a better summary."
        }
        
        self.metric_vars = {}
        
        for m, desc in metrics_info.items():
            row = ctk.CTkFrame(dialog, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)
            
            chk_var = tk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(row, text=m, variable=chk_var, width=130)
            chk.pack(side="left")
            
            # Help button (?)
            def show_help(metric_name=m, description=desc):
                messagebox.showinfo(f"Help: {metric_name}", description, parent=dialog)
                
            btn_help = ctk.CTkButton(row, text="?", width=20, height=20, corner_radius=10, 
                                     fg_color="transparent", border_width=1, 
                                     command=show_help)
            btn_help.pack(side="left", padx=(0, 15))
            
            ctk.CTkLabel(row, text="Threshold:").pack(side="left", padx=(10,5))
            thresh_var = tk.StringVar(value="0.5")
            ctk.CTkEntry(row, textvariable=thresh_var, width=50).pack(side="left")
            
            self.metric_vars[m] = {"selected": chk_var, "threshold": thresh_var}
            
        # --- CUSTOM METRICS FROM LIBRARY ---
        custom_metrics = []
        if CUSTOM_METRICS_DIR.exists():
            for fpath in CUSTOM_METRICS_DIR.glob("*.json"):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "name" in data and "criteria" in data:
                            custom_metrics.append(data)
                except Exception:
                    pass
                    
        if custom_metrics:
            ctk.CTkLabel(dialog, text="Custom Metrics (GEval):", font=("Arial", 12, "bold"), text_color="#5cb85c").pack(pady=(15, 5))
            
            for c_metric in custom_metrics:
                m_name = c_metric["name"]
                m_desc = c_metric["criteria"]
                m_thresh_def = str(c_metric.get("default_threshold", 1.0))
                
                row = ctk.CTkFrame(dialog, fg_color="transparent")
                row.pack(fill="x", padx=20, pady=5)
                
                chk_var = tk.BooleanVar(value=False)
                chk = ctk.CTkCheckBox(row, text=m_name, variable=chk_var, width=130, text_color="#5cb85c")
                chk.pack(side="left")
                
                def show_custom_help(metric_name=m_name, description=m_desc):
                    messagebox.showinfo(f"Criterion: {metric_name}", description, parent=dialog)
                    
                btn_help = ctk.CTkButton(row, text="?", width=20, height=20, corner_radius=10, 
                                         fg_color="transparent", border_width=1, text_color="#5cb85c",
                                         command=show_custom_help)
                btn_help.pack(side="left", padx=(0, 15))
                
                ctk.CTkLabel(row, text="Threshold:").pack(side="left", padx=(10,5))
                thresh_var = tk.StringVar(value=m_thresh_def)
                ctk.CTkEntry(row, textvariable=thresh_var, width=50).pack(side="left")
                
                self.metric_vars[m_name] = {"selected": chk_var, "threshold": thresh_var, "is_custom": True, "criteria": m_desc}
                
        def save_policy():
            selected_metrics = []
            for m, vars in self.metric_vars.items():
                if vars["selected"].get():
                    try:
                        t_val = float(vars["threshold"].get())
                    except ValueError:
                        t_val = 0.5
                    
                    metric_dict = {"name": m, "threshold": t_val}
                    if vars.get("is_custom"):
                        metric_dict["criteria"] = vars["criteria"]
                        
                    selected_metrics.append(metric_dict)
                    
            if not selected_metrics:
                messagebox.showwarning("Warning", "You must select at least one metric.", parent=dialog)
                return
                
            custom_policy = {
                "profile_name": "Interactive Custom Profile",
                "description": "Custom policy generated via UI wizard",
                "domain": "General Assistant",
                "recommended_model": "Any",
                "metrics": selected_metrics
            }
            
            save_path = filedialog.asksaveasfilename(title="Save YAML Policy", defaultextension=".yaml", filetypes=[("YAML Files", "*.yaml *.yml")], parent=dialog)
            if save_path:
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        yaml.dump(custom_policy, f, sort_keys=False)
                    self.profile_path_var.set(save_path)
                    messagebox.showinfo("Success", f"Policy saved at:\n{save_path}", parent=dialog)
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Could not save: {e}", parent=dialog)
                    
        ctk.CTkButton(dialog, text="Save and Use", command=save_policy, font=("Arial", 12, "bold")).pack(pady=20)

    # --- BATCH LOGIC ---
    def select_dataset(self):
        path = filedialog.askopenfilename(title="Select Dataset", filetypes=[("Supported Files", "*.csv *.xlsx *.json")])
        if path:
            self.dataset_path_var.set(path)
            
    def select_outdir(self):
        path = filedialog.askdirectory(title="Select Destination Folder for Results")
        if path:
            self.outdir_path_var.set(path)

    def on_save_project(self):
        try:
            name = self.proj_name_var.get().strip()
            if not name: raise ValueError("The project name is mandatory.")
            prov = self.provider_var.get()
            if prov == "Select provider...": raise ValueError("You must select a valid provider.")
                
            config = ProjectConfig(
                version="1.0",
                name=name,
                provider=prov,
                model=self.model_var.get(),
                profile_path=Path(self.profile_path_var.get()),
                dataset_path=Path(self.dataset_path_var.get()),
                output_dir=Path(self.outdir_path_var.get())
            )
            
            out_file = config.output_dir / "project.json"
            config_dict = {
                "version": config.version,
                "created_with": config.created_with,
                "name": config.name,
                "provider": config.provider,
                "model": config.model,
                "profile_path": str(config.profile_path),
                "dataset_path": str(config.dataset_path),
                "output_dir": str(config.output_dir)
            }
            
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=4)
                
            messagebox.showinfo("Success", f"Configuration successfully saved to:\n{out_file}")
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e))
        except Exception as e:
            messagebox.showerror("Unexpected Error", str(e))

    def on_run_batch(self):
        name = self.proj_name_var.get().strip()
        dataset_path = self.dataset_path_var.get()
        outdir_path = self.outdir_path_var.get()
        profile_path = self.profile_path_var.get()
        provider = self.provider_var.get()
        model = self.model_var.get()
        
        if not name or not dataset_path or not outdir_path:
            messagebox.showwarning("Warning", "You must configure Project Name, Dataset and Destination Folder.")
            return
            
        if not profile_path or not Path(profile_path).exists():
            messagebox.showwarning("Warning", "You must select a valid YAML profile in the side panel.")
            return
            
        if provider == "Select provider..." or not model or model.startswith("Esperando"):
            messagebox.showwarning("Warning", "You must configure provider and model in the side panel.")
            return
            
        self.btn_run_batch.configure(state="disabled", text="⏳ Evaluating Batch...")
        self.txt_batch_logs.configure(state="normal")
        self.txt_batch_logs.delete("1.0", "end")
        self.txt_batch_logs.insert("end", "[INFO] ", "info_tag")
        self.txt_batch_logs.insert("end", f"Loading project: {name}\n", "yellow_tag")
        self.txt_batch_logs.configure(state="disabled")
        
        # Save project config first (ignore UI popups by calling a silent version or just call it)
        # We will just start the thread. ProjectConfig is built in the thread anyway.
        
        threading.Thread(target=self._run_batch_thread, daemon=True).start()

    def _batch_progress_callback(self, idx, total, results_for_case):
        def update_ui():
            self.txt_batch_logs.configure(state="normal")
            
            if idx == 1:
                self.txt_batch_logs.insert("end", "[INFO] ", "info_tag")
                self.txt_batch_logs.insert("end", f"Dataset loaded: {total} rows found.\n", "yellow_tag")
                
            self.txt_batch_logs.insert("end", "[INFO] ", "info_tag")
            self.txt_batch_logs.insert("end", f"Running evaluation... ({idx}/{total})\n", "yellow_tag")
            
            metrics_str = " | ".join([f"{r.metric_name}: {r.score:.2f}" for r in results_for_case])
            passed = all(r.passed for r in results_for_case)
            
            if passed:
                msg = f"[OK] Case {idx} -> {metrics_str} -> PASSED\n"
                self.txt_batch_logs.insert("end", msg, "ok_tag")
            else:
                failed_r = next((r for r in results_for_case if not r.passed), results_for_case[0])
                self.txt_batch_logs.insert("end", "[WARNING] ", "warning_tag")
                self.txt_batch_logs.insert("end", f"Case {idx} -> {metrics_str} -> FAILED (threshold: {failed_r.threshold})\n", "error_tag")
                
            self.txt_batch_logs.see("end")
            self.txt_batch_logs.configure(state="disabled")
        self.after(0, update_ui)

    def _run_batch_thread(self):
        try:
            # 1. Inject API Key
            provider = self.provider_var.get()
            env_var = get_env_var_name(provider)
            api_key = self.api_key_var.get().strip() or os.environ.get(env_var, "")
            if provider.lower() == "groq": os.environ["OPENAI_API_KEY"] = api_key
            elif provider.lower() in ["google", "gemini"]: os.environ["GOOGLE_API_KEY"] = api_key
            
            # 2. Config & Adapter
            config = ProjectConfig(
                version="1.0",
                name=self.proj_name_var.get().strip(),
                provider=provider,
                model=self.model_var.get(),
                profile_path=Path(self.profile_path_var.get()),
                dataset_path=Path(self.dataset_path_var.get()),
                output_dir=Path(self.outdir_path_var.get())
            )
            adapter = DeepEvalAdapter(provider=config.provider, model=config.model)
            engine = EvaluatorEngine(config=config, adapter=adapter)
            
            # 3. Run
            audit_result = engine.run_audit(progress_callback=self._batch_progress_callback)
            
            # 4. Reports
            self.after(0, lambda: self._log_batch_msg("Generating Excel and HTML reports..."))
            ExcelReporter.export(audit_result, config.output_dir)
            template_path = project_root / "templates" / "report_template.html"
            HTMLReporter.export(audit_result, config.output_dir, template_path)
            
            self.after(0, lambda: self._batch_finished(success=True, msg=f"Audit completed successfully!\nCheck the folder: {config.output_dir}"))
            
        except Exception as e:
            self.after(0, lambda: self._batch_finished(success=False, msg=str(e)))
            
    def _log_batch_msg(self, msg):
        self.txt_batch_logs.configure(state="normal")
        self.txt_batch_logs.insert("end", f"{msg}\n")
        self.txt_batch_logs.see("end")
        self.txt_batch_logs.configure(state="disabled")

    def _batch_finished(self, success, msg):
        self._log_batch_msg("EXECUTION FINISHED." if success else f"ERROR: {msg}")
        self.btn_run_batch.configure(state="normal", text="▶ Start Batch Audit")
        if success:
            messagebox.showinfo("Audit Finished", msg)
        else:
            messagebox.showerror("Audit Error", msg)

    # --- MANUAL LOGIC ---
    def on_eval_manual(self):
        input_text = self.txt_input.get("1.0", "end-1c").strip()
        actual_output = self.txt_output.get("1.0", "end-1c").strip()
        profile_path = self.profile_path_var.get()
        provider = self.provider_var.get()
        model = self.model_var.get()
        
        if not input_text or not actual_output:
            messagebox.showwarning("Warning", "You must enter both Input and Actual Output.")
            return
            
        if not profile_path or not Path(profile_path).exists():
            messagebox.showwarning("Warning", "You must select a valid YAML profile in the side panel.")
            return
            
        if provider == "Select provider..." or not model or model.startswith("Esperando"):
            messagebox.showwarning("Warning", "You must configure provider and model in the side panel.")
            return
            
        self.btn_eval_manual.configure(state="disabled", text="Evaluating...")
        self.txt_results.configure(state="normal")
        self.txt_results.delete("1.0", "end")
        self.txt_results.insert("end", "Starting evaluation...\n")
        self.txt_results.configure(state="disabled")
        
        threading.Thread(target=self._run_manual_eval_thread, 
                         args=(input_text, actual_output, profile_path, provider, model), 
                         daemon=True).start()
                         
    def _run_manual_eval_thread(self, input_text, actual_output, profile_path, provider, model):
        try:
            env_var = get_env_var_name(provider)
            api_key = self.api_key_var.get().strip() or os.environ.get(env_var, "")
            
            if provider.lower() == "groq": os.environ["OPENAI_API_KEY"] = api_key
            elif provider.lower() in ["google", "gemini"]: os.environ["GOOGLE_API_KEY"] = api_key
                
            loader = ProfileLoader()
            profile = loader.load_profile(Path(profile_path))
            
            adapter = DeepEvalAdapter(provider=provider, model=model)
            results = adapter.evaluate_case("manual_test", input_text, actual_output, profile.metrics)
            
            self.after(0, self._update_manual_results, results, None)
        except Exception as e:
            self.after(0, self._update_manual_results, None, str(e))
            
    def _update_manual_results(self, results, error):
        self.txt_results.configure(state="normal")
        self.txt_results.delete("1.0", "end")
        
        if error:
            self.txt_results.insert("end", f"Error during evaluation:\n{error}\n")
        elif results:
            all_passed = all(r.passed for r in results)
            status_general = "✅ PASS" if all_passed else "❌ FAIL"
            
            self.txt_results.insert("end", f"Overall Result: {status_general}\n")
            self.txt_results.insert("end", "-" * 50 + "\n\n")
            
            for res in results:
                status = "✅ PASS" if res.passed else "❌ FAIL"
                self.txt_results.insert("end", f"Metric: {res.metric_name} | Verdict: {status}\n")
                self.txt_results.insert("end", f"Score: {res.score} (Threshold: {res.threshold})\n")
                self.txt_results.insert("end", f"Severity: {res.severity}\n")
                self.txt_results.insert("end", f"Reason:\n{res.reason}\n\n")
        else:
            self.txt_results.insert("end", "No metric results obtained.\n")
            
        self.txt_results.configure(state="disabled")
        self.btn_eval_manual.configure(state="normal", text="Evaluate Case Manually")

    # --- GEVAL LOGIC ---
    def setup_geval_tab(self):
        self.tab_geval.grid_rowconfigure(2, weight=1)
        self.tab_geval.grid_columnconfigure(0, weight=1)
        self.tab_geval.grid_columnconfigure(1, weight=1)
        
        # Texto instructivo arriba
        instr = "💡 Instructions: Define a custom criterion (GEval) in the left column and test it with the texts on the right.\nYou don't need to have a YAML Policy selected, the engine will exclusively test the rule you write here."
        ctk.CTkLabel(self.tab_geval, text=instr, text_color="gray", justify="left").grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 10), sticky="w")
        
        # --- LEFT COL: GEVAL CONFIG ---
        frame_geval_conf = ctk.CTkFrame(self.tab_geval)
        frame_geval_conf.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        
        ctk.CTkLabel(frame_geval_conf, text="Metric Name:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.geval_name_var = tk.StringVar(value="MyCustomRule")
        ctk.CTkEntry(frame_geval_conf, textvariable=self.geval_name_var).pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame_geval_conf, text="Criterion (Natural Language):", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.txt_geval_criteria = ctk.CTkTextbox(frame_geval_conf, height=100)
        self.txt_geval_criteria.pack(fill="both", expand=True, padx=10, pady=5)
        self.txt_geval_criteria.insert("1.0", "E.g.: The response must not contain Arabic numerals.")
        
        row_thr = ctk.CTkFrame(frame_geval_conf, fg_color="transparent")
        row_thr.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(row_thr, text="Threshold (0.0 a 1.0):", font=("Arial", 12, "bold")).pack(side="left")
        self.geval_thresh_var = tk.StringVar(value="1.0")
        ctk.CTkEntry(row_thr, textvariable=self.geval_thresh_var, width=60).pack(side="left", padx=10)
        
        # --- RIGHT COL: TEST CASE ---
        frame_geval_test = ctk.CTkFrame(self.tab_geval)
        frame_geval_test.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")
        
        ctk.CTkLabel(frame_geval_test, text="Input (Prompt):", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.txt_geval_input = ctk.CTkTextbox(frame_geval_test, height=80)
        self.txt_geval_input.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame_geval_test, text="Actual Output (Output to evaluate):", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.txt_geval_output = ctk.CTkTextbox(frame_geval_test, height=80)
        self.txt_geval_output.pack(fill="x", padx=10, pady=5)
        
        # --- BOTTOM ACTION ---
        btn_frame = ctk.CTkFrame(self.tab_geval, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        self.btn_save_geval = ctk.CTkButton(btn_frame, text="Save to Library", command=self.on_save_geval)
        self.btn_save_geval.pack(side="left", padx=10)
        
        self.btn_eval_geval = ctk.CTkButton(btn_frame, text="▶ Test Criterion On The Fly", command=self.on_eval_geval, font=("Arial", 14, "bold"), fg_color="#5cb85c", hover_color="#4cae4c")
        self.btn_eval_geval.pack(side="right", padx=10)
        
        # --- RESULTADOS ---
        ctk.CTkLabel(self.tab_geval, text="DeepEval Engine Results:", font=("Arial", 12, "bold")).grid(row=3, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="w")
        self.txt_geval_results = ctk.CTkTextbox(self.tab_geval, state="disabled", height=120)
        self.txt_geval_results.grid(row=4, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="nsew")
        self.tab_geval.grid_rowconfigure(4, weight=1)

    def on_save_geval(self):
        name = self.geval_name_var.get().strip()
        criteria = self.txt_geval_criteria.get("1.0", "end-1c").strip()
        try:
            t_val = float(self.geval_thresh_var.get())
        except:
            t_val = 1.0
            
        if not name or not criteria:
            messagebox.showwarning("Warning", "You must fill in the name and criterion.")
            return
            
        save_path = CUSTOM_METRICS_DIR / f"{name}.json"
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump({
                    "name": name,
                    "criteria": criteria,
                    "default_threshold": t_val
                }, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Success", f"Criterion saved to Library:\n{name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save: {e}")

    def on_eval_geval(self):
        input_text = self.txt_geval_input.get("1.0", "end-1c").strip()
        actual_output = self.txt_geval_output.get("1.0", "end-1c").strip()
        provider = self.provider_var.get()
        model = self.model_var.get()
        name = self.geval_name_var.get().strip()
        criteria = self.txt_geval_criteria.get("1.0", "end-1c").strip()
        
        try:
            thresh = float(self.geval_thresh_var.get())
        except:
            thresh = 1.0
        
        if not input_text or not actual_output or not name or not criteria:
            messagebox.showwarning("Warning", "You must fill in Name, Criterion, Input and Actual Output.")
            return
            
        if provider == "Select provider..." or not model or model.startswith("Esperando"):
            messagebox.showwarning("Warning", "You must configure provider and model in the side panel.")
            return
            
        self.btn_eval_geval.configure(state="disabled", text="Evaluating...")
        self.txt_geval_results.configure(state="normal")
        self.txt_geval_results.delete("1.0", "end")
        self.txt_geval_results.insert("end", "Starting evaluation of criterion on the fly...\n")
        self.txt_geval_results.configure(state="disabled")
        
        threading.Thread(target=self._run_geval_thread, 
                         args=(input_text, actual_output, provider, model, name, criteria, thresh), 
                         daemon=True).start()
                         
    def _run_geval_thread(self, input_text, actual_output, provider, model, name, criteria, thresh):
        try:
            env_var = get_env_var_name(provider)
            api_key = self.api_key_var.get().strip() or os.environ.get(env_var, "")
            if provider.lower() == "groq": os.environ["OPENAI_API_KEY"] = api_key
            elif provider.lower() in ["google", "gemini"]: os.environ["GOOGLE_API_KEY"] = api_key
                
            adapter = DeepEvalAdapter(provider=provider, model=model)
            
            # Build GEval metric config on the fly
            mc = MetricConfig(name=name, threshold=thresh, criteria=criteria)
            results = adapter.evaluate_case("geval_test", input_text, actual_output, [mc])
            
            self.after(0, self._update_geval_results, results, None)
        except Exception as e:
            self.after(0, self._update_geval_results, None, str(e))
            
    def _update_geval_results(self, results, error):
        self.txt_geval_results.configure(state="normal")
        self.txt_geval_results.delete("1.0", "end")
        
        if error:
            self.txt_geval_results.insert("end", f"Error during evaluation:\n{error}\n")
        elif results:
            res = results[0]
            status = "✅ PASS" if res.passed else "❌ FAIL"
            self.txt_geval_results.insert("end", f"Verdict: {status}\n")
            self.txt_geval_results.insert("end", f"Score: {res.score} (Threshold: {res.threshold})\n")
            self.txt_geval_results.insert("end", f"LLM Reasoning:\n{res.reason}\n")
        else:
            self.txt_geval_results.insert("end", "No results obtained.\n")
            
        self.txt_geval_results.configure(state="disabled")
        self.btn_eval_geval.configure(state="normal", text="▶ Test Criterion On The Fly")

if __name__ == "__main__":
    app = App()
    app.mainloop()
