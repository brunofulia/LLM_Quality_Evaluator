from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from engine.evaluation.domain_models import AuditResult

console = Console()

def render_welcome_banner():
    """Prints the application banner."""
    title = Text("LLM Quality Evaluator", style="bold cyan", justify="center")
    subtitle = Text("\nInteractive Audit Session", style="italic white", justify="center")
    title.append(subtitle)
    
    panel = Panel(
        title,
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(panel)
    console.print()

def render_audit_summary(audit_result: AuditResult):
    """Renders a beautiful summary table of the audit results."""
    
    # Group results by metric
    metrics_map = {}
    for case in audit_result.case_results:
        if case.metric_name not in metrics_map:
            metrics_map[case.metric_name] = []
        metrics_map[case.metric_name].append(case)
        
    for metric_name, cases in metrics_map.items():
        if not cases: continue
        threshold = cases[0].threshold
        table = Table(title=f"[ {metric_name} - Threshold: {threshold} ]", show_header=True, header_style="bold magenta")
        
        table.add_column("Case ID", justify="center")
        table.add_column("Input snippet", max_width=30)
        table.add_column("Severity", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Passed", justify="center")
        
        for case in cases:
            snippet = case.input_text[:27] + "..." if len(case.input_text) > 30 else case.input_text
            
            sev_color = "green"
            if case.severity == "MINOR_ISSUE":
                sev_color = "yellow"
            elif case.severity == "MAJOR_ISSUE":
                sev_color = "orange3"
            elif case.severity == "CRITICAL_AUDIT_FAILURE":
                sev_color = "bold red"
                
            passed_str = "[bold green]YES[/]" if case.passed else "[bold red]NO[/]"
                
            table.add_row(
                case.case_id,
                snippet,
                f"[{sev_color}]{case.severity}[/]",
                f"{case.score:.2f}",
                passed_str
            )
            
        console.print(table)
        console.print() # Add space between tables
    
    # Global metrics
    metrics = f"Provider: [bold cyan]{audit_result.provider}[/] | Model: [bold cyan]{audit_result.model}[/]\n"
    metrics += f"Total Cases: {audit_result.total_cases} | Pass Rate: {audit_result.pass_rate:.1f}%\n"
    metrics += f"Passed: [green]{audit_result.passed_cases}[/] | Failed: [red]{audit_result.failed_cases}[/]"
    
    console.print(Panel(metrics, title="Global Metrics", border_style="blue"))

def render_critical_ko():
    """Prints a critical failure alert."""
    alert = Text("CRITICAL KO DETECTED", style="bold white on red", justify="center")
    alert.append("\n\nThe audit failed due to strict policy violations.", style="red")
    console.print(Panel(alert, border_style="red"))
    
def render_success():
    """Prints a success alert."""
    alert = Text("AUDIT PASSED", style="bold white on green", justify="center")
    alert.append("\n\nNo critical policy violations detected.", style="green")
    console.print(Panel(alert, border_style="green"))
