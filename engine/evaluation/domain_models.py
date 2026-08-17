from dataclasses import dataclass, field
from typing import List

@dataclass(frozen=True)
class TestCaseResult:
    case_id: str
    metric_name: str
    input_text: str
    actual_output: str
    passed: bool
    severity: str  # PASS, MINOR_ISSUE, MAJOR_ISSUE, CRITICAL_AUDIT_FAILURE
    score: float
    threshold: float
    reason: str

@dataclass
class AuditResult:
    project_name: str
    provider: str
    model: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    critical_failures: int
    execution_time_seconds: float
    case_results: List[TestCaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed_cases / self.total_cases * 100) if self.total_cases > 0 else 0.0

    @property
    def has_critical_ko(self) -> bool:
        return self.critical_failures > 0
