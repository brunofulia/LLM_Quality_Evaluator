import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Since cli.py is at the root and not in a package, we need to import it properly.
# The tests run with PYTHONPATH root, so `import cli` works.
import cli

@patch("cli.DeepEvalAdapter")
@patch("cli.ProjectLoader.load_project")
@patch("cli.EvaluatorEngine")
@patch("cli.ExcelReporter.export")
@patch("cli.HTMLReporter.export")
def test_cli_success(mock_html, mock_excel, mock_engine_class, mock_load_project, mock_adapter_class, tmp_path):
    # Setup mocks
    mock_config = MagicMock()
    mock_config.provider = "openai"
    mock_config.model = "gpt"
    mock_config.output_dir = str(tmp_path)
    mock_load_project.return_value = mock_config
    
    mock_audit_result = MagicMock()
    mock_audit_result.has_critical_ko = False
    
    mock_engine_instance = MagicMock()
    mock_engine_instance.run_audit.return_value = mock_audit_result
    mock_engine_class.return_value = mock_engine_instance
    
    # Mock sys.argv and sys.exit
    test_args = ["cli.py", "dummy_project.json"]
    with patch.object(sys, 'argv', test_args):
        # We also need to patch Path.exists to pass the file check
        with patch.object(Path, 'exists', return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
                
            # Assert successful exit
            assert exc_info.value.code == 0
            
    # Assert integrations
    mock_load_project.assert_called_once()
    mock_engine_instance.run_audit.assert_called_once()
    mock_excel.assert_called_once()
    mock_html.assert_called_once()

@patch("cli.DeepEvalAdapter")
@patch("cli.ProjectLoader.load_project")
@patch("cli.EvaluatorEngine")
@patch("cli.ExcelReporter.export")
@patch("cli.HTMLReporter.export")
def test_cli_critical_ko(mock_html, mock_excel, mock_engine_class, mock_load_project, mock_adapter_class, tmp_path):
    # Setup mocks
    mock_config = MagicMock()
    mock_config.provider = "openai"
    mock_config.model = "gpt"
    mock_config.output_dir = str(tmp_path)
    mock_load_project.return_value = mock_config
    
    mock_audit_result = MagicMock()
    mock_audit_result.has_critical_ko = True # Critical KO
    
    mock_engine_instance = MagicMock()
    mock_engine_instance.run_audit.return_value = mock_audit_result
    mock_engine_class.return_value = mock_engine_instance
    
    test_args = ["cli.py", "dummy_project.json"]
    with patch.object(sys, 'argv', test_args):
        with patch.object(Path, 'exists', return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
                
            # Assert failure exit
            assert exc_info.value.code == 1

def test_cli_missing_project_file():
    test_args = ["cli.py", "does_not_exist.json"]
    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exc_info:
            cli.main()
            
        assert exc_info.value.code == 1

@patch("ui.tui.main.run_tui")
def test_cli_no_args(mock_run_tui):
    test_args = ["cli.py"]
    with patch.object(sys, 'argv', test_args):
        # cli.main should call run_tui and then exit cleanly or just return if it doesn't sys.exit itself
        with pytest.raises(SystemExit) as exc_info:
            mock_run_tui.side_effect = SystemExit(0)
            cli.main()
            
        assert exc_info.value.code == 0
