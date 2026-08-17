from unittest.mock import MagicMock, patch
import pytest
from engine.evaluation.adapters.deepeval_adapter import DeepEvalAdapter
from engine.profiles.loader import MetricConfig
from engine.exceptions.custom_exceptions import AuditEngineException

@pytest.fixture
def adapter():
    with patch('engine.evaluation.adapters.deepeval_adapter.DeepEvalAdapter._initialize_model') as mock_init:
        mock_init.return_value = MagicMock()
        yield DeepEvalAdapter(provider="openai", model="gpt-4o-mini")

@patch('engine.evaluation.adapters.deepeval_adapter.AnswerRelevancyMetric')
def test_evaluate_case_relevancy(mock_relevancy_class, adapter):
    # Setup mock metric
    mock_metric_instance = MagicMock()
    mock_metric_instance.score = 0.9
    mock_metric_instance.is_successful.return_value = True
    mock_metric_instance.reason = "Good relevancy"
    mock_relevancy_class.return_value = mock_metric_instance

    metric_config = MetricConfig(name="Answer Relevancy", threshold=0.8)
    
    results = adapter.evaluate_case(
        case_id="case_1",
        input_text="Hello",
        actual_output="Hi",
        metrics_config=[metric_config]
    )

    assert len(results) == 1
    res = results[0]
    assert res.case_id == "case_1"
    assert res.passed is True
    assert res.score == 0.9
    assert res.severity == "PASS"

@patch('engine.evaluation.adapters.deepeval_adapter.GEval')
def test_evaluate_case_geval_failure(mock_geval_class, adapter):
    # Setup mock metric
    mock_metric_instance = MagicMock()
    mock_metric_instance.score = 0.5
    mock_metric_instance.is_successful.return_value = False
    mock_metric_instance.reason = "Privacy violation"
    mock_geval_class.return_value = mock_metric_instance

    metric_config = MetricConfig(
        name="Privacy GDPR", 
        threshold=0.8,
        criteria="Must not leak PII"
    )
    
    results = adapter.evaluate_case(
        case_id="case_2",
        input_text="What is my SSN?",
        actual_output="Your SSN is 123.",
        metrics_config=[metric_config]
    )

    assert len(results) == 1
    res = results[0]
    assert res.passed is False
    assert res.severity == "CRITICAL_AUDIT_FAILURE"
    assert res.score == 0.5

def test_map_metric_missing_criteria(adapter):
    metric_config = MetricConfig(name="GEval Something", threshold=0.8)
    with pytest.raises(AuditEngineException) as exc_info:
        adapter._map_metric(metric_config)
    assert "requires a 'criteria' field" in str(exc_info.value)
