"""One repository per aggregate. Repositories map ORM rows to contract models."""

from backend.app.repositories.customer_repository import (
    CorruptCustomerRecordError,
    CustomerRepository,
)

__all__ = ["CorruptCustomerRecordError", "CustomerRepository"]
