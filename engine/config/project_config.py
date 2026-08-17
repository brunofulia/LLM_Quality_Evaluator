from pathlib import Path
from pydantic import BaseModel, Field, field_validator

class ProjectConfig(BaseModel):
    version: str = Field(..., description="Project contract schema version")
    created_with: str = Field(default="LLM Quality Evaluator 1.0")
    name: str = Field(..., description="Human-readable audit session name")
    provider: str = Field(default="openai")
    model: str = Field(default="gpt-4o-mini")
    profile_path: Path = Field(..., description="Path to YAML evaluation policy")
    dataset_path: Path = Field(..., description="Path to CSV/XLSX/JSON audit dataset")
    output_dir: Path = Field(..., description="Target directory for reports")

    @field_validator("profile_path", "dataset_path")
    def validate_file_exists(cls, path_val: Path) -> Path:
        if not path_val.exists():
            raise ValueError(f"Target audit resource not found: {path_val}")
        return path_val
