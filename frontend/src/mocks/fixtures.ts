// Contract-shaped example responses (docs/API_CONTRACTS.md, contracts/models.py).
// Synthetic data only. Used by MSW in development (VITE_USE_MOCKS=true) and in tests.
import type {
  AuditEvent,
  CustomerProfile,
  CustomerSummary,
  PolicyDecision,
  ReviewItem,
  SegmentName,
} from "../types";

const POLICY_VERSIONS = { policy: "1.0", segments: "1.0", offers: "1.0" };
const AS_OF = "2026-11-01";
const T0 = "2026-11-01T09:00:00Z";

export const profiles: CustomerProfile[] = [
  {
    customer_id: "CUST-001",
    first_name: "Asha",
    consent_marketing: true,
    plan: "Unlimited 499",
    months_active: 26,
    activity_score_30d: 88,
    activity_score_prev_30d: 84,
    on_time_payments_12m: 12,
    bill_status: "paid",
    days_overdue: 0,
    amount_due: "0.00",
    due_date: null,
    last_contacted_days_ago: 40,
  },
  {
    customer_id: "CUST-002",
    first_name: "Ravi",
    consent_marketing: false,
    plan: "Basic 199",
    months_active: 8,
    activity_score_30d: 20,
    activity_score_prev_30d: 65,
    on_time_payments_12m: 7,
    bill_status: "paid",
    days_overdue: 0,
    amount_due: "0.00",
    due_date: null,
    last_contacted_days_ago: null,
  },
  {
    customer_id: "CUST-003",
    first_name: "Meera",
    consent_marketing: true,
    plan: "Family 799",
    months_active: 14,
    activity_score_30d: 60,
    activity_score_prev_30d: 62,
    on_time_payments_12m: 10,
    bill_status: "overdue",
    days_overdue: 12,
    amount_due: "799.00",
    due_date: "2026-10-20",
    last_contacted_days_ago: 30,
  },
];

const primarySegments: Record<string, SegmentName | null> = {
  "CUST-001": "loyalty_candidate",
  "CUST-002": "declining",
  "CUST-003": "payment_reminder",
};

export function summaryOf(profile: CustomerProfile): CustomerSummary {
  return {
    customer_id: profile.customer_id,
    first_name: profile.first_name,
    plan: profile.plan,
    bill_status: profile.bill_status,
    consent_marketing: profile.consent_marketing,
    primary_segment: primarySegments[profile.customer_id] ?? null,
  };
}

export const decisions: Record<string, PolicyDecision> = {
  "CUST-001": {
    customer_id: "CUST-001",
    status: "draft_allowed",
    block_reasons: [],
    classification: {
      customer_id: "CUST-001",
      as_of_date: AS_OF,
      primary_segment: "loyalty_candidate",
      policy_versions: POLICY_VERSIONS,
      segments: [
        {
          segment: "loyalty_candidate",
          confidence: 0.9,
          reasons: [
            {
              code: "LONG_TENURE",
              description: "Active for at least 24 months.",
              evidence: { months_active: 26, threshold: 24 },
            },
            {
              code: "ON_TIME_PAYER",
              description: "Paid every bill on time in the last 12 months.",
              evidence: { on_time_payments_12m: 12 },
            },
          ],
        },
        {
          segment: "consistent",
          confidence: 0.7,
          reasons: [
            {
              code: "STABLE_ACTIVITY",
              description: "Activity steady versus the previous 30 days.",
              evidence: { activity_score_30d: 88, activity_score_prev_30d: 84 },
            },
          ],
        },
      ],
    },
    strategy: {
      segment: "loyalty_candidate",
      objective: "Thank and reward a long-standing customer.",
      tone: "warm",
      tone_guidance: "Appreciative, personal, no pressure.",
      offer_allowed: true,
    },
    offer_checks: [
      { offer_id: "LOYAL-10", eligible: true, failed_rules: [] },
      { offer_id: "DATA-5GB", eligible: false, failed_rules: ["segment_not_targeted"] },
    ],
    facts: {
      customer_id: "CUST-001",
      first_name: "Asha",
      plan: "Unlimited 499",
      segment: "loyalty_candidate",
      objective: "Thank and reward a long-standing customer.",
      tone: "warm",
      tone_guidance: "Appreciative, personal, no pressure.",
      offer: {
        offer_id: "LOYAL-10",
        description: "10% off the next bill",
        value: "10",
        unit: "percent",
        expiry: "2026-12-31",
        channel: "email",
      },
      reminder: null,
    },
  },
  "CUST-002": {
    customer_id: "CUST-002",
    status: "blocked",
    block_reasons: ["no_marketing_consent"],
    classification: {
      customer_id: "CUST-002",
      as_of_date: AS_OF,
      primary_segment: "declining",
      policy_versions: POLICY_VERSIONS,
      segments: [
        {
          segment: "declining",
          confidence: 0.8,
          reasons: [
            {
              code: "ACTIVITY_DROP",
              description: "Activity fell sharply versus the previous 30 days.",
              evidence: { activity_score_30d: 20, activity_score_prev_30d: 65 },
            },
          ],
        },
      ],
    },
    strategy: null,
    offer_checks: [],
    facts: null,
  },
  "CUST-003": {
    customer_id: "CUST-003",
    status: "draft_allowed",
    block_reasons: [],
    classification: {
      customer_id: "CUST-003",
      as_of_date: AS_OF,
      primary_segment: "payment_reminder",
      policy_versions: POLICY_VERSIONS,
      segments: [
        {
          segment: "payment_reminder",
          confidence: 1,
          reasons: [
            {
              code: "BILL_OVERDUE",
              description: "Bill is overdue.",
              evidence: { bill_status: "overdue", days_overdue: 12 },
            },
          ],
        },
      ],
    },
    strategy: {
      segment: "payment_reminder",
      objective: "Remind the customer of an overdue bill.",
      tone: "polite_firm",
      tone_guidance: "Clear and respectful; state the amount and date exactly.",
      offer_allowed: false,
    },
    offer_checks: [],
    facts: {
      customer_id: "CUST-003",
      first_name: "Meera",
      plan: "Family 799",
      segment: "payment_reminder",
      objective: "Remind the customer of an overdue bill.",
      tone: "polite_firm",
      tone_guidance: "Clear and respectful; state the amount and date exactly.",
      offer: null,
      reminder: {
        stage: "second_notice",
        days_overdue: 12,
        amount_due: "799.00",
        currency: "INR",
        due_date: "2026-10-20",
        support_path: "Reply to this email or call the support line in your account.",
      },
    },
  },
};

const CHECKS = [
  "schema_invalid",
  "amount_mismatch",
  "date_mismatch",
  "unknown_offer",
  "ineligible_offer",
  "unsupported_claim",
  "blocked_term",
  "missing_support_path",
  "consent_gap",
  "duplicate_outreach",
  "sensitive_data",
] as const;

export function passingValidation(): NonNullable<ReviewItem["validation"]> {
  return { passed: true, findings: [], checks_run: [...CHECKS], validator_version: "1.0" };
}

export function failingValidation(term: string): NonNullable<ReviewItem["validation"]> {
  return {
    passed: false,
    findings: [
      {
        code: "blocked_term",
        severity: "blocking",
        message: `Draft uses the blocked term "${term}".`,
        evidence: { term },
      },
    ],
    checks_run: [...CHECKS],
    validator_version: "1.0",
  };
}

function message(id: string, customerId: string, subject: string, body: string) {
  return {
    message_id: id,
    customer_id: customerId,
    draft: { subject, body },
    source: "llm" as const,
    provider: "mock",
    model: "mock-model",
    prompt_version: "1.0",
    generated_at: T0,
  };
}

export function initialReviews(): ReviewItem[] {
  return [
    {
      review_id: "REV-001",
      customer_id: "CUST-001",
      status: "pending_review",
      revision: 1,
      decision: decisions["CUST-001"],
      message: message(
        "MSG-001",
        "CUST-001",
        "Thank you, Asha: 10% off your next bill",
        "Hi Asha,\n\nThank you for being with us on Unlimited 499. Enjoy 10% off your next bill until 2026-12-31.\n\n<b>not html</b>",
      ),
      validation: passingValidation(),
      decisions: [],
      created_at: T0,
      updated_at: T0,
    },
    {
      review_id: "REV-002",
      customer_id: "CUST-003",
      status: "blocked",
      revision: 1,
      decision: decisions["CUST-003"],
      message: message(
        "MSG-002",
        "CUST-003",
        "Final warning: pay now",
        "Hi Meera,\n\nYour bill of INR 799.00 was due on 2026-10-20. Pay now or face legal action.",
      ),
      validation: failingValidation("legal action"),
      decisions: [],
      created_at: T0,
      updated_at: T0,
    },
    {
      review_id: "REV-003",
      customer_id: "CUST-002",
      status: "blocked",
      revision: 1,
      decision: decisions["CUST-002"],
      message: null,
      validation: null,
      decisions: [],
      created_at: T0,
      updated_at: T0,
    },
  ];
}

export function initialAudit(): AuditEvent[] {
  return [
    {
      event_id: "EVT-002",
      event_type: "draft_validated",
      occurred_at: "2026-11-01T09:00:02Z",
      actor: "system",
      customer_id: "CUST-001",
      review_id: "REV-001",
      message_id: "MSG-001",
      policy_versions: POLICY_VERSIONS,
      prompt_version: "1.0",
      model: "mock-model",
      details: { passed: true, revision: 1 },
    },
    {
      event_id: "EVT-001",
      event_type: "policy_decided",
      occurred_at: "2026-11-01T09:00:00Z",
      actor: "system",
      customer_id: "CUST-001",
      review_id: null,
      message_id: null,
      policy_versions: POLICY_VERSIONS,
      prompt_version: null,
      model: null,
      details: { status: "draft_allowed" },
    },
  ];
}
