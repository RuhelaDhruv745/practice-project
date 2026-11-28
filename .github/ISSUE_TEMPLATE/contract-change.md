---
name: Contract or ownership change
about: Request a change to contracts/, API_CONTRACTS.md, DATA_DICTIONARY.md, shared config, or another member's files
title: "[contract] "
labels: contract-change
---

**Requested by (member / role):**
**Type:** <!-- contract change | edit another member's path | shared config (pyproject, requirements, .env.example) -->

### What needs to change
<!-- Exact model, field, endpoint, enum value or file path -->

### Why
<!-- The requirement or dependency that needs it; why it cannot be done inside your own paths or with a fake -->

### Impact
- **Members affected:**
- **Backward compatible?** <!-- yes / no; if no, how consumers migrate -->
- **Tests to update:**

### Architect decision
<!-- Filled in by the architect: approved / rejected / alternative, and the contract version bump -->
- [ ] Approved
- [ ] One PR updates `contracts/`, `docs/API_CONTRACTS.md`, `docs/DATA_DICTIONARY.md` and tests together
