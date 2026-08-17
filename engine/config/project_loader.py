import json
from pathlib import Path
from pydantic import ValidationError
from .project_config import ProjectConfig

class ProjectLoader:
    @staticmethod
    def load_project(project_json_path: str | Path) -> ProjectConfig:
        path = Path(project_json_path)
        if not path.exists():
            raise FileNotFoundError(f"Project config file not found: {path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Resolver rutas relativas respecto al directorio del project.json
            base_dir = path.parent
            for field in ["profile_path", "dataset_path", "output_dir"]:
                if field in data:
                    field_path = Path(data[field])
                    if not field_path.is_absolute():
                        data[field] = str(base_dir / field_path)
                        
            return ProjectConfig(**data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in {path}: {e}")
        except ValidationError as e:
            raise e

    @staticmethod
    def save_project(config: ProjectConfig, dest_path: str | Path):
        path = Path(dest_path)
        # Convert absolute paths to relative if possible
        data = config.model_dump()
        base_dir = path.parent
        
        for field in ["profile_path", "dataset_path", "output_dir"]:
            if field in data:
                try:
                    rel_path = Path(data[field]).relative_to(base_dir)
                    data[field] = str(rel_path).replace("\\", "/")
                except ValueError:
                    # If not relative to base_dir, keep absolute
                    data[field] = str(data[field]).replace("\\", "/")
                    
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
