import os
import html
from pathlib import Path
from engine.evaluation.domain_models import AuditResult
from engine.logger import get_logger

logger = get_logger(__name__)

class HTMLReporter:
    """
    Generates an interactive HTML dashboard from an AuditResult object.
    """

    @staticmethod
    def export(audit_result: AuditResult, output_dir: Path, template_path: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / "audit_report.html"

        if not template_path.exists():
            logger.error(f"HTML Template not found at {template_path}")
            raise FileNotFoundError(f"HTML Template not found at {template_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

        # Banner configuration
        if audit_result.has_critical_ko:
            banner = '<div class="ko-alert">CRITICAL KO DETECTED: Audit failed due to strict policy violations!</div>'
        else:
            banner = '<div class="success-alert">AUDIT PASSED: No critical policy violations detected.</div>'

        # Group results by metric
        from collections import defaultdict
        grouped_results = defaultdict(list)
        for case in audit_result.case_results:
            grouped_results[case.metric_name].append(case)

        # Generate tables HTML
        tables_content = ""
        for metric, cases in grouped_results.items():
            threshold = cases[0].threshold if cases else "N/A"
            table_html = f"""
            <div class="metric-section" style="margin-bottom: 40px;">
                <h3 style="background-color: #3498db; color: white; padding: 10px; border-radius: 4px;">{html.escape(metric)} - Threshold: {threshold}</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Case ID</th>
                            <th>Input</th>
                            <th>Output</th>
                            <th>Severity</th>
                            <th>Score</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for case in cases:
                safe_input = html.escape(case.input_text)
                safe_output = html.escape(case.actual_output)
                safe_reason = html.escape(case.reason)
                
                row_html = f"""
                        <tr class="row-{case.severity}">
                            <td>{html.escape(case.case_id)}</td>
                            <td>{safe_input}</td>
                            <td>{safe_output}</td>
                            <td>{case.severity}</td>
                            <td>{case.score:.2f}</td>
                            <td>{safe_reason}</td>
                        </tr>
                """
                table_html += row_html
                
            table_html += """
                    </tbody>
                </table>
            </div>
            """
            tables_content += table_html

        # Replace placeholders
        rendered = template_content.replace("{{PROJECT_NAME}}", html.escape(audit_result.project_name))
        rendered = rendered.replace("{{PROVIDER}}", html.escape(audit_result.provider))
        rendered = rendered.replace("{{MODEL}}", html.escape(audit_result.model))
        rendered = rendered.replace("{{PASS_RATE}}", f"{audit_result.pass_rate:.1f}")
        rendered = rendered.replace("{{TOTAL_CASES}}", str(audit_result.total_cases))
        rendered = rendered.replace("{{CRITICAL_FAILURES}}", str(audit_result.critical_failures))
        rendered = rendered.replace("{{EXEC_TIME}}", f"{audit_result.execution_time_seconds:.2f}")
        rendered = rendered.replace("{{KO_BANNER}}", banner)
        rendered = rendered.replace("{{TABLES_CONTENT}}", tables_content)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(rendered)

        logger.info(f"HTML report generated at {file_path}")
        return file_path
