import json
import pandas as pd
from pathlib import Path
from engine.exceptions.custom_exceptions import InvalidDatasetFormatException

class DatasetLoader:
    @staticmethod
    def load_dataset(file_path: str | Path) -> list[dict]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        ext = path.suffix.lower()
        if ext == '.csv':
            df = pd.read_csv(path)
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(path)
        elif ext == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Assuming JSON is a list of objects or a dict that can be converted to list of dicts
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # if format is {"data": [{...}]}
                if 'data' in data and isinstance(data['data'], list):
                    return data['data']
                return [data]
            else:
                raise InvalidDatasetFormatException("JSON dataset must be a list of records.")
        else:
            raise InvalidDatasetFormatException(f"Unsupported dataset format: {ext}. Supported formats are .csv, .xlsx, .json")
        
        # Replace NaNs with None/null for cleaner JSON compatibility
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient='records')
