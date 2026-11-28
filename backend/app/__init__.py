"""FastAPI application (Member 1).

Orchestrates the pipeline: profile -> PolicyEngine.decide -> DraftGenerator.generate
-> PolicyEngine.validate -> review item -> approval -> mock outbox, recording audit
events at each step. Depends on contracts.interfaces Protocols, never on concrete
implementations. Entry point backend/app/main.py is created by Member 1."""
