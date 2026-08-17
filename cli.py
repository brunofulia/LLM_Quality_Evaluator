import sys
import argparse
from pathlib import Path

from engine.config.project_loader import ProjectLoader
from engine.evaluation.adapters.deepeval_adapter import DeepEvalAdapter
from engine.evaluation.evaluator import EvaluatorEngine
from engine.exporters.excel_reporter import ExcelReporter
from engine.exporters.html_reporter import HTMLReporter
from engine.logger import get_logger

logger = get_logger("cli")

def main():
    parser = argparse.ArgumentParser(description="LLM Quality Evaluator CLI Wrapper")
    parser.add_argument("project_path", nargs="?", type=str, help="Path to project.json")
    
    args = parser.parse_args()

    # If no project_path provided, launch Interactive TUI
    if not args.project_path:
        try:
            from ui.tui.main import run_tui
            run_tui()
            return
        except ImportError as e:
            logger.error(f"Failed to load TUI: {e}")
            sys.exit(1)

    project_json_path = Path(args.project_path)
    
    if not project_json_path.exists():
        logger.error(f"Project file not found at {project_json_path}")
        sys.exit(1)
        
    try:
        # 1. Load Project Contract
        logger.info(f"Loading project from {project_json_path}")
        config = ProjectLoader.load_project(project_json_path)
        
        # 2. Initialize Engine & Adapter
        adapter = DeepEvalAdapter(provider=config.provider, model=config.model)
        engine = EvaluatorEngine(config=config, adapter=adapter)
        
        # 3. Run Audit
        audit_result = engine.run_audit()
        
        # 4. Export Evidences
        output_dir = Path(config.output_dir)
        
        # Excel Report
        ExcelReporter.export(audit_result, output_dir)
        
        # HTML Report
        template_path = Path("templates") / "report_template.html"
        HTMLReporter.export(audit_result, output_dir, template_path)
        
        # 5. Controlled KO Check
        if audit_result.has_critical_ko:
            logger.error("Audit finished with CRITICAL KO. Strict policies were violated.")
            sys.exit(1)
        else:
            logger.info("Audit finished successfully. No critical violations.")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error during execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
