import os
import pytest
from pathlib import Path
from engine.data.dataset_loader import DatasetLoader
from engine.exceptions.custom_exceptions import InvalidDatasetFormatException

PROJECTS_DIR = Path(__file__).parent.parent / "projects" / "sample_audit"

def test_load_csv():
    csv_path = PROJECTS_DIR / "dataset.csv"
    data = DatasetLoader.load_dataset(csv_path)
    assert len(data) == 3
    assert data[0]["id"] == 1
    assert "I want to reset my password." in data[0]["input"]

def test_load_json():
    json_path = PROJECTS_DIR / "dataset.json"
    data = DatasetLoader.load_dataset(json_path)
    assert len(data) == 3
    assert data[1]["id"] == 2
    assert "order 123" in data[1]["input"]

def test_load_xlsx():
    xlsx_path = PROJECTS_DIR / "dataset.xlsx"
    if not xlsx_path.exists():
        pytest.skip("dataset.xlsx not generated yet")
    data = DatasetLoader.load_dataset(xlsx_path)
    assert len(data) == 3
    assert data[2]["id"] == 3
    assert "John Doe" in data[2]["input"]

def test_identical_loading():
    csv_path = PROJECTS_DIR / "dataset.csv"
    json_path = PROJECTS_DIR / "dataset.json"
    xlsx_path = PROJECTS_DIR / "dataset.xlsx"

    csv_data = DatasetLoader.load_dataset(csv_path)
    json_data = DatasetLoader.load_dataset(json_path)
    
    assert csv_data == json_data
    
    if xlsx_path.exists():
        xlsx_data = DatasetLoader.load_dataset(xlsx_path)
        assert csv_data == xlsx_data

def test_invalid_format():
    invalid_path = PROJECTS_DIR / "dummy.txt"
    invalid_path.write_text("dummy")
    with pytest.raises(InvalidDatasetFormatException):
        DatasetLoader.load_dataset(invalid_path)
    invalid_path.unlink()
        
    invalid_ext = PROJECTS_DIR / "results"
    with pytest.raises((FileNotFoundError, IsADirectoryError, PermissionError, InvalidDatasetFormatException)):
        DatasetLoader.load_dataset(invalid_ext)
