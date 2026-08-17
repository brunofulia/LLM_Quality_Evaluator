from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
import yaml
from pathlib import Path
from engine.exceptions.custom_exceptions import ProfileValidationError

class MetricConfig(BaseModel):
    name: str = Field(..., description="Name of the metric")
    threshold: float = Field(..., description="Pass/Fail threshold between 0.0 and 1.0")
    criteria: Optional[str] = Field(None, description="Criteria for GEval metrics")

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {v}")
        return v

class ProfileConfig(BaseModel):
    profile_name: str = Field(..., description="Name of the evaluation policy")
    description: str = Field(..., description="Description of the policy")
    domain: str = Field(..., description="Business domain of the policy")
    recommended_model: str = Field(..., description="Recommended LLM for this policy")
    metrics: List[MetricConfig] = Field(default_factory=list, description="List of metrics to evaluate")

class ProfileLoader:
    @staticmethod
    def load_profile(profile_path: str | Path) -> ProfileConfig:
        path = Path(profile_path)
        if not path.exists():
            raise FileNotFoundError(f"Profile not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                 raise ProfileValidationError(f"Invalid profile format in {path}: expected a dictionary")
            
            return ProfileConfig(**data)
            
        except yaml.YAMLError as e:
            raise ProfileValidationError(f"Error parsing YAML in {path}: {str(e)}")
        except Exception as e:
            if isinstance(e, ProfileValidationError):
                raise e
            raise ProfileValidationError(f"Error validating profile {path}: {str(e)}")
