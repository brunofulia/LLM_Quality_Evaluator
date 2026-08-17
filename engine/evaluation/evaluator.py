import time
from typing import List, Dict, Any
from pathlib import Path
from engine.config.project_config import ProjectConfig
from engine.evaluation.domain_models import AuditResult, TestCaseResult
from engine.evaluation.adapters.base import BaseEvaluationAdapter
from engine.data.dataset_loader import DatasetLoader
from engine.profiles.loader import ProfileLoader
from engine.logger import get_logger

logger = get_logger(__name__)

class EvaluatorEngine:
    """
    Main Domain Orchestrator. 
    Coordinates the ingestion of the dataset, the loading of policies,
    and delegating the actual evaluation to the configured adapter.
    """
    def __init__(self, config: ProjectConfig, adapter: BaseEvaluationAdapter):
        self.config = config
        self.adapter = adapter
        self.dataset_loader = DatasetLoader()
        self.profile_loader = ProfileLoader()
        
    def run_audit(self, progress_callback=None) -> AuditResult:
        """
        Executes the evaluation loop for all cases in the dataset.
        If progress_callback is provided, it is called after each case:
        progress_callback(current_index, total_cases, case_result)
        """
        start_time = time.time()
        
        dataset = self.dataset_loader.load_dataset(self.config.dataset_path)
        profile = self.profile_loader.load_profile(self.config.profile_path)
        
        logger.info(f"Starting audit session: {profile.profile_name}")
        logger.info(f"Loading dataset from {self.config.dataset_path}")
        logger.info(f"Loading policy profile from {self.config.profile_path}")
        
        all_results: List[TestCaseResult] = []
        total_cases = len(dataset)
        passed_cases = 0
        failed_cases = 0
        critical_failures = 0
        
        for idx, row in enumerate(dataset, start=1):
            logger.info(f"Evaluating case {idx} ({idx}/{total_cases})")
            
            # Map input/output
            case_id = str(row.get("id", f"row_{idx}"))
            input_text = str(row.get("input", ""))
            actual_output = str(row.get("actual_output", ""))
            
            # Delegate to adapter
            results_for_case = self.adapter.evaluate_case(
                case_id=case_id,
                input_text=input_text,
                actual_output=actual_output,
                metrics_config=profile.metrics
            )
            
            all_results.extend(results_for_case)
            
            if progress_callback:
                progress_callback(idx, total_cases, results_for_case)
            
            # Check row-level success based on all metrics for this row
            row_passed = all(res.passed for res in results_for_case)
            if row_passed:
                passed_cases += 1
            else:
                failed_cases += 1
                
            # Check for critical failures in this row's metrics
            for res in results_for_case:
                if res.severity == "CRITICAL_AUDIT_FAILURE":
                    critical_failures += 1
                    logger.warning(f"CRITICAL KO detected on case {case_id} for metric {res.reason}")
        
        execution_time = time.time() - start_time
        logger.info(f"Audit completed in {execution_time:.2f} seconds.")
        
        # 5. Build and return AuditResult Domain Object
        return AuditResult(
            project_name=self.config.name,
            provider=self.config.provider,
            model=self.config.model,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            critical_failures=critical_failures,
            execution_time_seconds=execution_time,
            case_results=all_results
        )
