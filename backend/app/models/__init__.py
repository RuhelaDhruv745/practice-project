"""ORM models: internal storage only; the API speaks contract models."""

from backend.app.models.customer import (
    ActivityRow,
    BillingRecordRow,
    CommunicationPreferenceRow,
    CustomerRow,
)

__all__ = [
    "ActivityRow",
    "BillingRecordRow",
    "CommunicationPreferenceRow",
    "CustomerRow",
]
