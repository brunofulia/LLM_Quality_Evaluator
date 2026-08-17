import sys
import os
from pathlib import Path

# Add the root directory to sys.path so we can import 'ui' and 'engine'
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.console import Console

from ui.tui.file_picker import prompt_for_project_file, prompt_for_directory
from ui.tui.renderers import render_welcome_banner, render_audit_summary, render_critical_ko, render_success

from engine.config.project_loader import ProjectLoader
from engine.evaluation.adapters.deepeval_adapter import DeepEvalAdapter
from engine.evaluation.evaluator import EvaluatorEngine
from engine.exporters.excel_reporter import ExcelReporter
from engine.exporters.html_reporter import HTMLReporter
from engine.logger import get_logger

logger = get_logger("tui")
console = Console()

from engine.config.project_config import ProjectConfig
from engine.discovery.model_fetcher import ModelFetcher
import questionary

def run_tui():
    render_welcome_banner()
    
    mode = questionary.select(
        "Welcome to LLM Quality Evaluator. What would you like to do?",
        choices=[
            questionary.Choice("Load Existing Project (.json)", value="load"),
            questionary.Choice("Create New Audit Interactively (Wizard)", value="wizard")
        ]
    ).ask()
    
    if mode is None:
        sys.exit(0)
        
    if mode == "load":
        project_path = prompt_for_project_file(start_dir=".", extension=".json", prompt_text="Select project file")
        if not project_path:
            console.print("[yellow]Audit cancelled by user.[/]")
            sys.exit(0)
        console.print(f"\n[bold cyan]Selected project:[/] {project_path}")
        config = ProjectLoader.load_project(project_path)
    else:
        name = questionary.text("Enter a name for this audit session:", default="Interactive Audit").ask()
        
        console.print("\n[bold cyan]Step 1:[/] Select your dataset file (.csv)")
        dataset_path = prompt_for_project_file(start_dir=".", extension=".csv", prompt_text="Select dataset")
        if not dataset_path: sys.exit(0)
        
        console.print("\n[bold cyan]Step 2:[/] How do you want to configure your metrics?")
        policy_mode = questionary.select(
            "Select policy mode:",
            choices=[
                questionary.Choice("Select an existing policy file (.yaml)", value="existing"),
                questionary.Choice("Create a custom policy interactively", value="interactive")
            ]
        ).ask()
        
        if policy_mode == "existing":
            profile_path = prompt_for_project_file(start_dir=".", extension=".yaml", prompt_text="Select policy")
            if not profile_path: sys.exit(0)
        else:
            selected_metrics = questionary.checkbox(
                "Select the metrics you want to evaluate:",
                choices=["AnswerRelevancy", "Toxicity", "Bias", "Hallucination", "Summarization"]
            ).ask()
            
            if not selected_metrics:
                console.print("[yellow]No metrics selected. Audit cancelled.[/]")
                sys.exit(0)
                
            metrics_config = []
            for m in selected_metrics:
                t = questionary.text(f"Enter threshold for {m} (0.0 to 1.0):", default="0.5").ask()
                try:
                    threshold_val = float(t)
                except ValueError:
                    threshold_val = 0.5
                metrics_config.append({"name": m, "threshold": threshold_val})
                
            import yaml
            custom_policy = {
                "profile_name": "Interactive Custom Profile",
                "description": "Custom policy generated via wizard",
                "domain": "General Assistant",
                "recommended_model": "Any",
                "metrics": metrics_config
            }
            
            os.makedirs("temp", exist_ok=True)
            profile_path = "temp/custom_policy.yaml"
            with open(profile_path, "w", encoding="utf-8") as f:
                yaml.dump(custom_policy, f, sort_keys=False)
            console.print(f"[green]Generated custom policy at {profile_path}[/]")
        
        provider = questionary.select("\n[bold cyan]Step 3:[/] Select Provider:", choices=["google", "openai", "groq", "anthropic"]).ask()
        
        # We need the API key right now to fetch models
        provider_env_map = {
            "openai": "OPENAI_API_KEY",
            "google": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY"
        }
        provider_key = provider_env_map[provider]
        api_key = os.environ.get(provider_key)
        if not api_key:
            api_key = questionary.password(f"[{provider}] API Key not found. Please enter your {provider_key}:").ask()
            if not api_key: sys.exit(0)
            os.environ[provider_key] = api_key
            
        with console.status(f"[cyan]Fetching available models for {provider}...[/]"):
            try:
                models = ModelFetcher.fetch_models(provider, api_key)
            except ValueError as e:
                console.print(f"[red]{e}[/]")
                models = []
            
        if models:
            model = questionary.select("\n[bold cyan]Step 4:[/] Select Model:", choices=models).ask()
        else:
            model = questionary.text("\n[bold cyan]Step 4:[/] Could not fetch models. Enter model name manually:").ask()
            
        console.print("\n[bold cyan]Step 5:[/] Select output directory for reports:")
        output_dir = prompt_for_directory(start_dir=".", prompt_text="Select output directory")
        if not output_dir: sys.exit(0)
        
        config_data = {
            "version": "1.0",
            "name": name,
            "provider": provider,
            "model": model,
            "dataset_path": str(dataset_path),
            "profile_path": str(profile_path),
            "input_column": "input",
            "output_column": "actual_output",
            "output_dir": output_dir
        }
        config = ProjectConfig(**config_data)
        
        save = questionary.confirm("\nDo you want to save this configuration to a project.json file?").ask()
        if save:
            save_path = questionary.text("Enter filename:", default="project.json").ask()
            if save_path:
                ProjectLoader.save_project(config, save_path)
                console.print(f"[green]Saved configuration to {save_path}[/]")
    
    try:
        # Resolve API Key Injection (Required for both modes)
        provider_env_map = {
            "openai": "OPENAI_API_KEY",
            "gpt": "OPENAI_API_KEY",
            "google": "GEMINI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "grok": "GROK_API_KEY",
            "groq": "GROQ_API_KEY"
        }
        
        provider_key = provider_env_map.get(config.provider.lower())
        api_key = os.environ.get(provider_key)
        if provider_key and not api_key:
            api_key = questionary.password(f"[{config.provider}] API Key not found. Please enter your {provider_key}:").ask()
            if not api_key:
                console.print("[yellow]Audit cancelled by user (No API key provided).[/]")
                sys.exit(0)
            os.environ[provider_key] = api_key
            
        # If it is groq, we also copy to OPENAI_API_KEY to trick the OpenAI client
        if config.provider.lower() == "groq":
            os.environ["OPENAI_API_KEY"] = api_key or os.environ.get("GROQ_API_KEY", "")
        # If it is google/gemini, we inject GOOGLE_API_KEY in case langchain needs it
        elif config.provider.lower() in ["google", "gemini"]:
            os.environ["GOOGLE_API_KEY"] = api_key or os.environ.get("GEMINI_API_KEY", "")
            
        adapter = DeepEvalAdapter(provider=config.provider, model=config.model)
        engine = EvaluatorEngine(config=config, adapter=adapter)
        
        # 3. Execution (No progress bar to avoid logger flickering)
        console.print("\n[bold cyan]Starting audit execution...[/]")
        
        # Run engine without the custom rich progress callback
        audit_result = engine.run_audit()
        
        console.print("[green]Audit completed![/]")

        if not audit_result:
            raise ValueError("Audit returned no results.")

        # 4. Generate visual summary
        render_audit_summary(audit_result)
        
        # 5. Export Evidences
        console.print("\n[bold cyan]Generating physical reports...[/]")
        output_dir = Path(config.output_dir)
        
        excel_path = ExcelReporter.export(audit_result, output_dir)
        console.print(f"✅ Excel saved to: [green]{excel_path}[/]")
        
        template_path = Path("templates") / "report_template.html"
        html_path = HTMLReporter.export(audit_result, output_dir, template_path)
        console.print(f"✅ HTML saved to: [green]{html_path}[/]\n")
        
        # 6. Controlled KO Check
        if audit_result.has_critical_ko:
            render_critical_ko()
            sys.exit(1)
        else:
            render_success()
            sys.exit(0)
            
    except Exception as e:
        console.print(f"\n[bold red]Fatal error during execution:[/] {str(e)}")
        logger.error(f"TUI Error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run_tui()
