import pytest
from pathlib import Path
from pydantic import ValidationError
from engine.profiles.loader import ProfileLoader, ProfileConfig, MetricConfig
from engine.exceptions.custom_exceptions import ProfileValidationError
import yaml

PROFILES_DIR = Path(__file__).parent.parent / "profiles"

def test_load_valid_profile():
    profile_path = PROFILES_DIR / "customer_support_gdpr.yaml"
    profile = ProfileLoader.load_profile(profile_path)
    
    assert isinstance(profile, ProfileConfig)
    assert profile.profile_name == "Customer Support GDPR & Policy Gate"
    assert len(profile.metrics) == 2
    
    relevancy_metric = profile.metrics[0]
    assert relevancy_metric.name == "Answer Relevancy"
    assert relevancy_metric.threshold == 0.80

def test_invalid_threshold(tmp_path):
    invalid_yaml = """
profile_name: "Test"
description: "Test desc"
domain: "Test"
recommended_model: "gpt"
metrics:
  - name: "Answer Relevancy"
    threshold: 1.5
"""
    file_path = tmp_path / "invalid_thresh.yaml"
    file_path.write_text(invalid_yaml)
    
    with pytest.raises(ProfileValidationError) as exc_info:
        ProfileLoader.load_profile(file_path)
    
    assert "Threshold must be between 0.0 and 1.0" in str(exc_info.value)

def test_missing_required_fields(tmp_path):
    invalid_yaml = """
profile_name: "Test"
# missing description, etc
metrics: []
"""
    file_path = tmp_path / "missing.yaml"
    file_path.write_text(invalid_yaml)
    
    with pytest.raises(ProfileValidationError):
        ProfileLoader.load_profile(file_path)

def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        ProfileLoader.load_profile("does_not_exist.yaml")
