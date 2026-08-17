import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from engine.evaluation.domain_models import AuditResult, TestCaseResult
from ui.tui.file_picker import prompt_for_project_file
from ui.tui.renderers import render_audit_summary, render_critical_ko, render_success, render_welcome_banner
from ui.tui import main as tui_main

@pytest.fixture
def dummy_audit_result():
    res1 = TestCaseResult(case_id="1", metric_name="Toxicity", input_text="short", actual_output="safe", passed=True, severity="PASS", score=1.0, threshold=0.8, reason="ok")
    
    res2 = TestCaseResult(case_id="2", metric_name="Toxicity", input_text="this is a very long input text that should be truncated", actual_output="out", passed=False, severity="CRITICAL_AUDIT_FAILURE", score=0.1, threshold=0.8, reason="bad")
    return AuditResult(
        project_name="Test",
        provider="groq",
        model="llama-3",
        case_results=[res1, res2],
        total_cases=2,
        passed_cases=1,
        failed_cases=1,
        critical_failures=1,
        execution_time_seconds=1.23
    )

# --- Test Renderers ---
@patch("ui.tui.renderers.console.print")
def test_render_welcome_banner(mock_print):
    render_welcome_banner()
    assert mock_print.call_count == 2 # panel + empty line

@patch("ui.tui.renderers.console.print")
def test_render_critical_ko(mock_print):
    render_critical_ko()
    assert mock_print.call_count == 1

@patch("ui.tui.renderers.console.print")
def test_render_success(mock_print):
    render_success()
    assert mock_print.call_count == 1

@patch("ui.tui.renderers.console.print")
def test_render_audit_summary(mock_print, dummy_audit_result):
    render_audit_summary(dummy_audit_result)
    assert mock_print.call_count >= 2 # table + global metrics panel

# --- Test File Picker ---
@patch("ui.tui.file_picker.questionary")
def test_prompt_for_project_file_success(mock_questionary, tmp_path):
    # Setup dummy dir
    json_file = tmp_path / "project.json"
    json_file.write_text("{}")
    
    # Mock ask to return the file path
    mock_ask = MagicMock()
    mock_ask.ask.return_value = str(json_file)
    mock_questionary.select.return_value = mock_ask
    
    result = prompt_for_project_file(start_dir=str(tmp_path))
    assert result == json_file

@patch("ui.tui.file_picker.questionary")
def test_prompt_for_project_file_cancel(mock_questionary, tmp_path):
    mock_ask = MagicMock()
    mock_ask.ask.return_value = None # user pressed Ctrl+C
    mock_questionary.select.return_value = mock_ask
    
    result = prompt_for_project_file(start_dir=str(tmp_path))
    assert result is None

# --- Test TUI Main ---
@patch("ui.tui.main.sys.exit")
@patch("ui.tui.main.prompt_for_project_file")
@patch("ui.tui.main.questionary")
@patch("ui.tui.main.ProjectLoader")
@patch("ui.tui.main.DeepEvalAdapter")
@patch("ui.tui.main.EvaluatorEngine")
@patch("ui.tui.main.ExcelReporter.export")
@patch("ui.tui.main.HTMLReporter.export")
@patch("ui.tui.main.render_audit_summary")
def test_run_tui_success(
    mock_render_summary, mock_html, mock_excel, mock_engine_class, 
    mock_adapter, mock_loader, mock_questionary, mock_prompt, mock_exit, dummy_audit_result
):
    # Setup
    mock_mode = MagicMock()
    mock_mode.ask.return_value = "load"
    mock_questionary.select.return_value = mock_mode
    
    mock_prompt.return_value = Path("dummy.json")
    
    mock_config = MagicMock()
    mock_config.provider = "openai"
    mock_config.model = "gpt"
    mock_config.output_dir = "dummy_dir"
    mock_loader.load_project.return_value = mock_config
    
    # Success audit result
    dummy_audit_result_success = MagicMock()
    dummy_audit_result_success.has_critical_ko = False
    dummy_audit_result_success.pass_rate = 100.0
    dummy_audit_result_success.total_cases = 1
    dummy_audit_result_success.passed_cases = 1
    dummy_audit_result_success.failed_cases = 0
    dummy_audit_result_success.case_results = []
    
    mock_exit.side_effect = SystemExit(0)
    
    mock_engine = MagicMock()
    mock_engine.run_audit.return_value = dummy_audit_result_success
    mock_engine_class.return_value = mock_engine
    
    # Execute
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
        with pytest.raises(SystemExit):
            tui_main.run_tui()
    
    # Assertions
    mock_engine.run_audit.assert_called_once()
    mock_excel.assert_called_once()
    mock_html.assert_called_once()
    mock_exit.assert_called_with(0)

@patch("ui.tui.main.sys.exit")
@patch("ui.tui.main.prompt_for_project_file")
@patch("ui.tui.main.questionary")
@patch("ui.tui.main.ProjectLoader")
@patch("ui.tui.main.DeepEvalAdapter")
@patch("ui.tui.main.EvaluatorEngine")
@patch("ui.tui.main.ExcelReporter.export")
@patch("ui.tui.main.HTMLReporter.export")
@patch("ui.tui.main.render_critical_ko")
def test_run_tui_critical_ko(
    mock_render_ko, mock_html, mock_excel, mock_engine_class, 
    mock_adapter, mock_loader, mock_questionary, mock_prompt, mock_exit
):
    mock_mode = MagicMock()
    mock_mode.ask.return_value = "load"
    mock_questionary.select.return_value = mock_mode
    
    mock_prompt.return_value = Path("dummy.json")
    
    mock_config = MagicMock()
    mock_config.provider = "openai"
    mock_config.model = "gpt"
    mock_config.output_dir = "dummy_dir"
    mock_loader.load_project.return_value = mock_config
    
    dummy_audit_result_ko = MagicMock()
    dummy_audit_result_ko.has_critical_ko = True
    dummy_audit_result_ko.pass_rate = 50.0
    dummy_audit_result_ko.total_cases = 1
    dummy_audit_result_ko.passed_cases = 0
    dummy_audit_result_ko.failed_cases = 1
    dummy_audit_result_ko.case_results = []
    
    mock_exit.side_effect = SystemExit(1)
    
    mock_engine = MagicMock()
    mock_engine.run_audit.return_value = dummy_audit_result_ko
    mock_engine_class.return_value = mock_engine
    
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test_key"}):
        with pytest.raises(SystemExit):
            tui_main.run_tui()
    
    mock_render_ko.assert_called_once()
    mock_exit.assert_called_with(1)

@patch("ui.tui.main.sys.exit")
@patch("ui.tui.main.questionary")
@patch("ui.tui.main.prompt_for_project_file")
def test_run_tui_cancelled_by_user(mock_prompt, mock_questionary, mock_exit):
    mock_mode = MagicMock()
    mock_mode.ask.return_value = "load"
    mock_questionary.select.return_value = mock_mode
    
    mock_prompt.return_value = None
    mock_exit.side_effect = SystemExit(0)
    with pytest.raises(SystemExit):
        tui_main.run_tui()
    mock_exit.assert_called_with(0)

