import pytest
from unittest.mock import MagicMock
from pathlib import Path
from engine.evaluation.evaluator import EvaluatorEngine
from engine.config.project_config import ProjectConfig
from engine.evaluation.domain_models import TestCaseResult, AuditResult
from engine.profiles.loader import ProfileConfig, MetricConfig

@pytest.fixture
def mock_config():
    # Because ProjectConfig validates paths exist, we can mock or create dummy ones,
    # or we can mock ProjectConfig entirely if we only care about its attributes.
    # But since Pydantic does validation, let's create a MagicMock that acts like config.
    config = MagicMock(spec=ProjectConfig)
    config.name = "Test Audit"
    config.provider = "groq"
    config.model = "llama3"
    config.dataset_path = Path("dummy.csv")
    config.profile_path = Path("dummy.yaml")
    return config

def test_evaluator_engine(mock_config):
    # Setup mocks
    mock_adapter = MagicMock()
    
    engine = EvaluatorEngine(config=mock_config, adapter=mock_adapter)
    
    # Mock dataset
    engine.dataset_loader.load_dataset = MagicMock(return_value=[
        {"id": "1", "input": "in1", "actual_output": "out1"},
        {"id": "2", "input": "in2", "actual_output": "out2"}
    ])
    
    # Mock profile
    metric = MetricConfig(name="Rel", threshold=0.8)
    profile = ProfileConfig(
        profile_name="Test",
        description="Test",
        domain="Test",
        recommended_model="Test",
        metrics=[metric]
    )
    engine.profile_loader.load_profile = MagicMock(return_value=profile)
    
    # Mock adapter results
    # Case 1: PASS
    res1 = TestCaseResult(case_id="1", metric_name="AnswerRelevancy", input_text="in1", actual_output="out1", 
                          passed=True, severity="PASS", score=1.0, threshold=0.5, reason="ok")
    res2 = TestCaseResult(case_id="2", metric_name="AnswerRelevancy", input_text="in2", actual_output="out2", 
                          passed=False, severity="CRITICAL_AUDIT_FAILURE", score=0.0, threshold=0.5, reason="bad")
                          
    # side_effect allows different returns for sequential calls
    mock_adapter.evaluate_case.side_effect = [[res1], [res2]]
    
    # Run audit
    audit_result = engine.run_audit()
    
    assert isinstance(audit_result, AuditResult)
    assert audit_result.total_cases == 2
    assert audit_result.passed_cases == 1
    assert audit_result.failed_cases == 1
    assert audit_result.critical_failures == 1
    assert audit_result.has_critical_ko is True
    assert audit_result.pass_rate == 50.0
