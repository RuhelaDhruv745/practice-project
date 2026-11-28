# API and data contract rules

- `contracts/` (models, enums, `Protocol`s), `docs/API_CONTRACTS.md` and `docs/DATA_DICTIONARY.md` are architect-owned and frozen at baseline `1.0`.
- Import contract models; never redefine, subclass-to-extend or shadow them in a module.
- To change a contract: open a "Contract or ownership change" issue, get architect approval, then one PR updates `contracts/`, both docs and the tests together.
- Endpoint paths, status codes and `error.code` values must match `docs/API_CONTRACTS.md` exactly.
- Errors use the `ErrorResponse` shape. A policy refusal is a `201` result with `status: "blocked"`, not an error.
- Money is a decimal string in JSON; dates are ISO `YYYY-MM-DD`; timestamps ISO 8601 UTC.
- The React app generates TypeScript types from `/openapi.json`; do not hand-write diverging types.
- Approve is only valid for `pending_review` with passing validation and a `draft_allowed` decision; the backend re-validates before delivery.
