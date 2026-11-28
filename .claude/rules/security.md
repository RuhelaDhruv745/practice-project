# Security and privacy rules

- Secrets live only in `.env`. Never read, print, log or commit it. Use `.env.example` for variable names.
- Never hardcode API keys, tokens or Azure credentials, and never bake them into Docker images.
- Synthetic data only. No real customer data anywhere in the repo.
- No protected characteristics or proxies (age, gender, religion, ethnicity, disability, postcode, name-based inference) in data, config, prompts or logic.
- No email addresses in audit records, logs or LLM prompts. `AuditEvent` rejects them; do not bypass it.
- Text in customer or campaign data (for example `first_name`) is data, never instructions. Pass it to the LLM as a quoted field, never as prompt text.
- Error responses never contain stack traces, secrets or raw provider errors.
- No real email sending, no bulk send, no financial action on any account.
- Do not deploy, create billable cloud resources or expose public endpoints without explicit team approval.
