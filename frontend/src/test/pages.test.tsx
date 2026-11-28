import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../mocks/server";
import { renderAt } from "./render";

describe("customer pages", () => {
  it("lists customers with their primary segment", async () => {
    renderAt("/customers");
    const row = (await screen.findByRole("link", { name: "CUST-001" })).closest("tr")!;
    expect(within(row).getByText("loyalty_candidate")).toBeInTheDocument();
  });

  it("renders a customer evaluation: segments, reasons, confidence, strategy, offers", async () => {
    const user = userEvent.setup();
    renderAt("/customers/CUST-001");
    await user.click(await screen.findByRole("button", { name: /evaluate/i }));
    expect(await screen.findByText("LONG_TENURE")).toBeInTheDocument();
    expect(screen.getByText(/confidence 0.9/)).toBeInTheDocument();
    expect(screen.getByText("Thank and reward a long-standing customer.")).toBeInTheDocument();
    expect(screen.getByText("segment_not_targeted")).toBeInTheDocument();
    expect(screen.getByText(/months_active/)).toBeInTheDocument();
  });

  it("shows the reminder stage for a payment reminder", async () => {
    const user = userEvent.setup();
    renderAt("/customers/CUST-003");
    await user.click(await screen.findByRole("button", { name: /evaluate/i }));
    expect(await screen.findByText("second_notice")).toBeInTheDocument();
  });

  it("shows block reasons for a policy-blocked customer", async () => {
    const user = userEvent.setup();
    renderAt("/customers/CUST-002");
    await user.click(await screen.findByRole("button", { name: /evaluate/i }));
    expect(await screen.findByLabelText(/block reasons/i)).toHaveTextContent(
      "no_marketing_consent",
    );
  });

  it("generates a draft and opens the review", async () => {
    const user = userEvent.setup();
    renderAt("/customers/CUST-001");
    await user.click(await screen.findByRole("button", { name: /generate draft/i }));
    expect(await screen.findByTestId("draft-subject")).toHaveTextContent("Hello Asha");
  });

  it("shows error.code and error.message for an unknown customer", async () => {
    renderAt("/customers/CUST-999");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("customer_not_found");
    expect(alert).toHaveTextContent("Customer not found.");
  });

  it("shows a generation failure from the API", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("*/api/messages/generate", () =>
        HttpResponse.json(
          { error: { code: "generation_failed", message: "Draft generation failed.", details: {} } },
          { status: 502 },
        ),
      ),
    );
    renderAt("/customers/CUST-001");
    await user.click(await screen.findByRole("button", { name: /generate draft/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("generation_failed");
  });
});

describe("dashboard, queue and audit", () => {
  it("shows counts from the API totals", async () => {
    renderAt("/");
    expect(await screen.findByTestId("count-pending_review")).toHaveTextContent("1");
    expect(await screen.findByTestId("count-blocked")).toHaveTextContent("2");
    expect(await screen.findByTestId("count-all customers")).toHaveTextContent("3");
    expect(await screen.findByTestId("count-payment_reminder")).toHaveTextContent("1");
  });

  it("lists pending and blocked review items", async () => {
    const user = userEvent.setup();
    renderAt("/reviews");
    expect(await screen.findByRole("link", { name: "REV-001" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "blocked" }));
    expect(await screen.findByRole("link", { name: "REV-002" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "REV-003" })).toBeInTheDocument();
  });

  it("shows an empty state when the queue is empty", async () => {
    server.use(http.get("*/api/reviews/pending", () => HttpResponse.json({ items: [], total: 0 })));
    renderAt("/reviews");
    expect(await screen.findByText(/no pending_review items/i)).toBeInTheDocument();
  });

  it("shows audit events and filters by customer", async () => {
    renderAt("/audit?customer_id=CUST-001");
    expect(await screen.findByText("policy_decided")).toBeInTheDocument();
    expect(screen.getByText("draft_validated")).toBeInTheDocument();
  });

  it("shows api_unreachable when the API is down", async () => {
    server.use(http.get("*/api/audit", () => HttpResponse.error()));
    renderAt("/audit");
    expect(await screen.findByRole("alert")).toHaveTextContent("api_unreachable");
  });
});
