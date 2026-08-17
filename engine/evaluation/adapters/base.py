from abc import ABC, abstractmethod
from typing import List
from engine.evaluation.domain_models import TestCaseResult
from engine.profiles.loader import MetricConfig

class BaseEvaluationAdapter(ABC):
    """
    Abstract Base Class for LLM evaluation frameworks.
    Enforces a standard contract so the business logic is decoupled from
    the specific underlying framework (e.g., DeepEval, TruLens, Ragas).
    """

    @abstractmethod
    def evaluate_case(self, case_id: str, input_text: str, actual_output: str, metrics_config: List[MetricConfig]) -> List[TestCaseResult]:
        """
        Evaluates a single test case against a list of metric configurations.

        Args:
            case_id: The unique identifier of the test case.
            input_text: The input prompt sent to the LLM.
            actual_output: The generated response from the LLM.
            metrics_config: A list of metrics (and thresholds/criteria) to evaluate against.

        Returns:
            A list of TestCaseResult domain objects.
        """
        pass
