"""One repository per aggregate. Repositories map ORM rows to contract models."""

from backend.app.repositories.audit_repository import AuditRepository
from backend.app.repositories.customer_repository import (
    CorruptCustomerRecordError,
    CustomerRepository,
)
from backend.app.repositories.outbox_repository import OutboxRepository, append_jsonl
from backend.app.repositories.review_repository import ReviewRepository

__all__ = [
    "AuditRepository",
    "CorruptCustomerRecordError",
    "CustomerRepository",
    "OutboxRepository",
    "ReviewRepository",
    "append_jsonl",
]
