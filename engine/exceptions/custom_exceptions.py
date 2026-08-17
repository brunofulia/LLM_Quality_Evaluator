class AuditEngineException(Exception):
    """Base exception for all LLM Quality Evaluator domain errors."""
    pass


class InvalidDatasetFormatException(AuditEngineException):
    """Raised when the dataset format is unsupported or invalid."""
    pass


class ProfileValidationError(AuditEngineException):
    """Raised when the evaluation policy profile is invalid."""
    pass


class CriticalAuditFailureException(AuditEngineException):
    """Raised when a critical audit failure is detected (e.g. PII leak)."""
    pass
