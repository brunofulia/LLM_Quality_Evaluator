from typing import List
from engine.evaluation.adapters.base import BaseEvaluationAdapter
from engine.evaluation.domain_models import TestCaseResult
from engine.profiles.loader import MetricConfig
from engine.exceptions.custom_exceptions import AuditEngineException

# Import DeepEval metrics and models
from deepeval.metrics import AnswerRelevancyMetric, GEval, ToxicityMetric, BiasMetric, HallucinationMetric, SummarizationMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.models import GPTModel, GeminiModel, GrokModel, AnthropicModel

class DeepEvalAdapter(BaseEvaluationAdapter):
    """
    Adapter that isolates the 'deepeval' framework from our core business logic.
    """
    
    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini"):
        self.provider = provider.lower()
        self.model_name = model
        self.model = self._initialize_model(self.provider, self.model_name)
        
    def _initialize_model(self, provider: str, model_name: str):
        if provider == "google":
            return GeminiModel(model=model_name)
        elif provider == "groq":
            import os
            os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
            # Groq is compatible with OpenAI API, so we reuse GPTModel
            return GPTModel(model=model_name)
        elif provider == "anthropic":
            return AnthropicModel(model=model_name)
        else:
            return GPTModel(model=model_name)

    def evaluate_case(self, case_id: str, input_text: str, actual_output: str, metrics_config: List[MetricConfig]) -> List[TestCaseResult]:
        results: List[TestCaseResult] = []
        
        # Note: Hallucination and Summarization require context, passing empty list to avoid None errors
        test_case = LLMTestCase(
            input=input_text,
            actual_output=actual_output,
            context=[input_text] # Default fallback for metrics needing context
        )

        for mc in metrics_config:
            deepeval_metric = self._map_metric(mc)
            
            try:
                # Execute the metric evaluation with auto-retry for free tiers
                import time
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        deepeval_metric.measure(test_case)
                        break
                    except Exception as loop_e:
                        error_msg = str(loop_e).lower()
                        # Retry on rate limits OR pydantic validation errors (bad JSON from LLM)
                        if (("429" in error_msg or "resource_exhausted" in error_msg or "validation error" in error_msg) 
                            and attempt < max_retries - 1):
                            time.sleep(5) # Shorter sleep for parsing errors
                            continue
                        raise loop_e
                
                # Extract results
                score = deepeval_metric.score if deepeval_metric.score is not None else 0.0
                passed = deepeval_metric.is_successful()
                reason = deepeval_metric.reason if deepeval_metric.reason else "No reason provided by engine."
                
                # Determine severity based on business rules
                severity = self._determine_severity(passed, mc.name)
                
                result = TestCaseResult(
                    case_id=case_id,
                    metric_name=mc.name,
                    input_text=input_text,
                    actual_output=actual_output,
                    passed=passed,
                    severity=severity,
                    score=score,
                    threshold=mc.threshold,
                    reason=reason
                )
                results.append(result)

            except Exception as e:
                # Catch framework-specific errors gracefully instead of crashing the entire audit
                # This ensures the rest of the cases can continue evaluating.
                fallback_result = TestCaseResult(
                    case_id=case_id,
                    metric_name=mc.name,
                    input_text=input_text,
                    actual_output=actual_output,
                    passed=False,
                    severity="CRITICAL_AUDIT_FAILURE",
                    score=0.0,
                    threshold=mc.threshold,
                    reason=f"Evaluation Engine Error: {str(e)}"
                )
                results.append(fallback_result)
                
        return results

    def _map_metric(self, mc: MetricConfig):
        """Maps our generic MetricConfig to a specific DeepEval Metric object."""
        name_upper = mc.name.upper()
        
        if "RELEVANCY" in name_upper:
            return AnswerRelevancyMetric(threshold=mc.threshold, model=self.model)
        elif "GEVAL" in name_upper or mc.criteria:
            if not mc.criteria:
                raise AuditEngineException(f"GEval metric '{mc.name}' requires a 'criteria' field.")
            return GEval(
                name=mc.name,
                criteria=mc.criteria,
                evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
                threshold=mc.threshold,
                model=self.model
            )
        elif "TOXICITY" in name_upper:
            return ToxicityMetric(threshold=mc.threshold, model=self.model)
        elif "BIAS" in name_upper:
            return BiasMetric(threshold=mc.threshold, model=self.model)
        elif "HALLUCINATION" in name_upper:
            return HallucinationMetric(threshold=mc.threshold, model=self.model)
        elif "SUMMARIZATION" in name_upper:
            return SummarizationMetric(threshold=mc.threshold, model=self.model)
        else:
             raise AuditEngineException(f"Unsupported metric type: {mc.name}")

    def _determine_severity(self, passed: bool, metric_name: str) -> str:
        """
        Determines the business severity of a failure.
        - PASS: successful
        - CRITICAL_AUDIT_FAILURE: GEval privacy/policy failures
        - MAJOR_ISSUE: standard failures (relevancy, etc.)
        """
        if passed:
            return "PASS"
        
        name_upper = metric_name.upper()
        if "PRIVACY" in name_upper or "POLICY" in name_upper or "GDPR" in name_upper:
            return "CRITICAL_AUDIT_FAILURE"
            
        return "MAJOR_ISSUE"
