# Customer Loyalty and Engagement Assistant: Problem Statement

Nov 28, 2026 · @Vansh Gupta

## Background

Sending every customer the same message wastes the best relationships and annoys the rest. Retail and telecom companies serve customers who differ in loyalty, plan usage, engagement and payment habits, yet campaigns often treat them alike.

The usual results are easy to see. Loyal customers get no thanks, inactive customers get offers that do not fit them, and a customer who is two days late on a bill gets the same stern tone as one who is a month late.

Generative AI can write personalised messages quickly, but used carelessly it can invent an offer, quote a wrong amount, ignore consent or sound disrespectful. A usable solution must therefore combine fast drafting with strict, checkable rules and a human who approves each message.

## Problem statement

Build a GenAI assistant that sorts customers into segments using only permitted data, then drafts a matching email that a human reviews before anything is sent.

The assistant must decide facts with code and use the language model only for wording. Segment, offer eligibility, billing stage, amounts and dates come from deterministic rules. The model receives those verified facts and writes a subject and body. Every draft is then checked, and a failed check blocks it.

The intended flow for one customer is:

1. Assemble a minimal profile from permitted fields: activity, plan, payment status, contact history and consent.
2. Assign one or more segments with reason codes and a confidence value.
3. Pick an approved objective and tone for the segment, such as thanks, reward, re-engagement or a payment reminder.
4. Check offer eligibility, reminder stage and contact rules in code. If consent is missing or the customer was contacted too recently, stop and record why.
5. Ask the model to draft a subject and body from the verified facts only.
6. Validate the draft against the data, the offer terms and the blocked-language list.
7. Show the evidence and draft to a reviewer, who approves, edits or rejects it.
8. On approval, write the message to a mock outbox and record an audit entry.

## Users and scenarios

Two people use the assistant: a campaign reviewer who approves each draft, and a policy owner who maintains segments, offers, tones and blocked language in configuration files.

The system must handle these six cases, including one it refuses.

| Scenario | Signal in the data | Segment | Message goal | Expected result |
|---|---|---|---|---|
| Consistent customer | Steady activity, all payments on time | Consistent | Thank the customer | Draft with thanks, no hard sell |
| Loyalty candidate | Long tenure, high activity, on-time payments | Loyalty candidate | Reward | Draft with one eligible reward |
| Declining activity | Activity well below the previous 30 days | Declining | Re-engage | Draft with a relevant engagement offer |
| Inactive customer | Very low or no recent activity | Dormant | Win back | Gentle draft with an eligible offer |
| Overdue bill | Bill overdue by a known number of days | Payment reminder | Collect politely | Reminder whose firmness follows the stage, with a support or dispute path |
| No consent or contacted too recently | Marketing consent missing, or recent outreach | Any | None | Blocked, with the reason recorded |

## Goals and expected outcomes

The assistant should make each customer message relevant, accurate and safe to send, while keeping a person in control.

- **Relevance:** every customer gets a segment that explains why, and a message tone that fits it.
- **Accuracy:** every amount, date and offer in an approved draft matches the source data.
- **Safety:** drafts that break a rule are blocked before review, not after sending.
- **Control:** nothing leaves the system without reviewer approval.
- **Traceability:** every decision can be reconstructed from an audit record.
- **Reproducibility:** another person can rerun the build and get the same segments and checks.

## Functional requirements

The system must meet these ten requirements, each with a clear test of when it is done.

| ID | Capability | Requirement | Done when |
|---|---|---|---|
| FR-01 | Customer profile | Build a minimal profile from permitted fields only | Profile contains no unnecessary or protected data |
| FR-02 | Segmentation | Assign segments with reason codes and a confidence value | Every segment shows why it was chosen |
| FR-03 | Strategy selection | Map each segment to an approved objective and tone from configuration | Changing the config changes the strategy without code edits |
| FR-04 | Offer and reward checks | Validate eligibility, offer ID, value, expiry and channel in code | Ineligible offers never reach the draft |
| FR-05 | Billing reminders | Choose a reminder stage from days overdue, keeping a respectful tone and a support path | Stage matches the overdue days in every test |
| FR-06 | Grounded drafting | Generate subject and body only from verified facts | No invented amount, date or offer appears |
| FR-07 | Safety and compliance checks | Detect unsupported claims, blocked language, consent gaps and duplicate outreach | A bad draft is marked blocked with findings |
| FR-08 | Human review | Show evidence, segment, strategy, draft and findings with approve, edit and reject | Each reviewer action is saved |
| FR-09 | Audit | Record versions, evidence fields, decisions and outcome without storing email addresses | A decision can be reconstructed from the log |
| FR-10 | Controlled delivery | Send only to a mock outbox, and only after approval and passing checks | Sending is impossible when any check fails |

## Rules the system must follow

These rules are not optional, and each one must be enforced in code or checked by a test.

- **Code decides facts.** Segment, eligibility, billing stage, amounts and dates are computed by deterministic rules, never by the model.
- **The model only words.** It receives verified facts and returns a subject and body as structured output. It does not choose offers or reminder stages.
- **Every draft is checked.** Numbers, dates and offer IDs in the text must match the input data, blocked terms must be absent, and reminders must include a support or dispute path.
- **A person approves.** No message is sent without reviewer approval, and a failed check blocks sending.
- **Fair treatment.** Protected characteristics and proxies for them must not affect offers, rewards or reminder severity, and must not appear in the data.
- **Consent and frequency.** Missing consent or recent contact blocks outreach.
- **Privacy.** Audit records exclude email addresses and other unnecessary personal data.
- **Untrusted text.** Any text in customer or campaign data that looks like an instruction is treated as data, not as a command.
- **Safe delivery.** Sending is a mock that writes to a local outbox. No real email is sent.

## Data and assumptions

The build uses about 15 synthetic customers in one CSV file, three offers and a small policy configuration. No real customer data is used, and every threshold below is an assumption that lives in a config file and can be changed.

### Customer fields

| Field | Meaning |
|---|---|
| `customer_id`, `first_name` | Identifier and name used in the greeting |
| `consent_marketing` | Whether marketing contact is allowed |
| `plan`, `months_active` | Current plan and tenure |
| `activity_score_30d`, `activity_score_prev_30d` | Recent and previous activity, used to detect decline |
| `on_time_payments_12m` | Count of on-time payments in the last 12 months |
| `bill_status`, `days_overdue`, `amount_due`, `due_date` | Billing facts used for reminders |
| `last_contacted_days_ago` | Used to block duplicate outreach |

The table has no age, gender, religion or similar fields.

### Assumed rules (editable)

- **Declining activity:** activity down at least 30% against the previous 30 days.
- **Dormant:** activity score below a low threshold set in the config.
- **Loyalty candidate:** tenure and on-time payment counts above set minimums, with no overdue bill.
- **Reminder stages:** courteous for 1 to 7 days overdue, firmer for 8 to 21 days, final notice from 22 days, each with a support path.
- **Duplicate outreach:** blocked if the customer was contacted within a set number of days.
- **Offers:** each has an ID, value, expiry date, allowed segments, minimum tenure and channel.

## Scope boundaries

The project drafts and reviews messages. It does not send them to real customers or act on accounts.

### In scope

- Rule-based segmentation with reason codes
- Deterministic offer, billing-stage and contact checks
- LLM drafting from verified facts, with output validation
- A review screen with approve, edit and reject
- A mock outbox, an audit log and a short evaluation

### Out of scope

- Real email delivery and bulk sending without review
- Charging, waiving or changing any customer's account or payment
- Machine-learned segmentation or churn prediction
- Real customer data, and any use of protected characteristics
- Integration with real CRM or billing systems

## Success measures and evaluation

Success means the system gets segments right, writes only what the data supports and blocks what it should. The targets below are proposals for this practice build, and only metrics that were actually run are reported, with the number of test cases stated.

| Measure | How it is measured | Proposed target |
|---|---|---|
| Segment accuracy | Predicted segment against a labelled scenario set | All six scenarios correct |
| Grounded drafts | Every amount, date and offer ID in a draft matches the data | No mismatches in approved drafts |
| Validator catch rate | Deliberately bad drafts (invented offer, wrong amount, blocked term) run through the validators | Every bad draft blocked |
| Blocked cases | No-consent and recently-contacted customers | Blocked every time, with a reason |
| Reminder stage | Days overdue against the chosen stage | Correct in every test |
| Reviewer rubric | Reviewer scores relevance, clarity, tone and call to action from 1 to 5 | Reported as an average, with the sample size |

Known limitations are listed with the results: synthetic data, a small scenario set and rule thresholds that were assumed, not learned.

## Deliverables and risks

The project ships a working prototype, its configuration and the evidence that it behaves safely.

### Deliverables

1. A Streamlit app that takes a customer, shows the segment and reasons, and produces a reviewable draft.
2. Configuration files for segments, offers, tones, reminder stages and blocked terms.
3. A reviewer screen showing evidence, strategy, draft, validation findings and approve, edit or reject buttons.
4. An evaluation report covering the six scenarios and the measures above.
5. A README with architecture, data contract, assumptions, setup and run steps.
6. A demo showing all six scenarios, including one blocked message.

### Risks and fallbacks

| Risk | Fallback |
|---|---|
| Free LLM rate limits or an outage | Retry with backoff, cache responses during development, and switch provider through configuration |
| Model returns malformed or off-policy text | Parse structured output safely, retry once, and let the validators block the draft |
| Rules are too rigid or too loose | Keep thresholds in config and show reason codes so a reviewer can see why |
| Time runs short | Cut the edit button and deployment polish first, and keep validators, the blocked case and the audit log |

## Open question for the client

Should a customer with an overdue bill but no marketing consent still receive a payment reminder, given that a reminder is a service message and not marketing?
