"""FastAPI application (Member 1).

Orchestrates the pipeline: profile -> PolicyEngine.decide -> DraftGenerator.generate
-> PolicyEngine.validate -> review item -> approval -> mock outbox, recording audit
events at each step. Depends on contracts.interfaces Protocols, never on concrete
implementations. The app factory is ``backend.app.main.create_app``."""

__version__ = "0.1.0"
