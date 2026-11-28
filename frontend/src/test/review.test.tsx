import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "../mocks/server";
import { renderAt } from "./render";

const approveButton = () => screen.queryByRole("button", { name: /approve and deliver/i });

describe("review detail", () => {
  it("renders the draft as text, never as HTML", async () => {
    renderAt("/reviews/REV-001");
    const body = await screen.findByTestId("draft-body");
    expect(body.textContent).toContain("<b>not html</b>");
    expect(body.querySelector("b")).toBeNull();
  });

  it("approves a pending item with a passing validation and shows the outbox record", async () => {
    const user = userEvent.setup();
    let sent: unknown;
    server.events.on("request:start", async ({ request }) => {
      if (request.url.endsWith("/approve")) sent = await request.clone().json();
    });
    renderAt("/reviews/REV-001");
    await screen.findByTestId("draft-subject");
    const rubric = screen.getByRole("group", { name: /rubric/i });
    for (const select of within(rubric).getAllByRole("combobox")) {
      await user.selectOptions(select, "4");
    }
    await user.click(approveButton()!);
    expect(await screen.findByText(/delivered to the mock outbox/i)).toBeInTheDocument();
    expect(sent).toMatchObject({
      reviewer_id: "reviewer-1",
      rubric: { relevance: 4, clarity: 4, personalisation: 4, call_to_action: 4, tone: 4 },
    });
    // Delivered items offer no further actions.
    expect(approveButton()).toBeNull();
    expect(screen.queryByRole("button", { name: /^reject$/i })).toBeNull();
    server.events.removeAllListeners();
  });

  it("disables approve while the rubric is only partly filled", async () => {
    const user = userEvent.setup();
    renderAt("/reviews/REV-001");
    await screen.findByTestId("draft-subject");
    const rubric = screen.getByRole("group", { name: /rubric/i });
    await user.selectOptions(within(rubric).getAllByRole("combobox")[0], "3");
    expect(approveButton()).toBeDisabled();
  });

  it("shows a 409 from the API instead of crashing", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("*/api/reviews/:id/approve", () =>
        HttpResponse.json(
          {
            error: {
              code: "review_not_approvable",
              message: "Validation failed; draft cannot be approved.",
              details: { status: "pending_review" },
            },
          },
          { status: 409 },
        ),
      ),
    );
    renderAt("/reviews/REV-001");
    await screen.findByTestId("draft-subject");
    await user.click(approveButton()!);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("review_not_approvable");
    expect(alert).toHaveTextContent("Validation failed; draft cannot be approved.");
  });

  it("displays blocking validation findings and offers no approve button", async () => {
    renderAt("/reviews/REV-002");
    const findings = await screen.findByRole("list", { name: /validation findings/i });
    expect(findings).toHaveTextContent("blocked_term");
    expect(findings).toHaveTextContent("blocking");
    expect(approveButton()).toBeNull();
    expect(screen.getByTestId("approve-unavailable")).toHaveTextContent(/validation failed/i);
  });

  it("never offers approve or edit for an item blocked by policy", async () => {
    renderAt("/reviews/REV-003");
    expect(await screen.findByLabelText(/block reasons/i)).toHaveTextContent(
      "no_marketing_consent",
    );
    expect(approveButton()).toBeNull();
    expect(screen.queryByRole("button", { name: /save edit/i })).toBeNull();
    expect(screen.getByTestId("approve-unavailable")).toHaveTextContent(/blocked by policy/i);
  });

  it("sends edits through PATCH and shows the re-validation result", async () => {
    const user = userEvent.setup();
    renderAt("/reviews/REV-002");
    const body = await screen.findByLabelText(/^body$/i);
    await user.clear(body);
    await user.type(body, "Hi Meera, your bill of INR 799.00 was due on 2026-10-20.");
    await user.click(screen.getByRole("button", { name: /save edit and re-validate/i }));

    expect(await screen.findByText(/re-validated revision 2/i)).toBeInTheDocument();
    await waitFor(() => expect(approveButton()).toBeInTheDocument());
    expect(screen.getByTestId("draft-body")).toHaveTextContent("INR 799.00");
  });

  it("shows a failed re-validation and keeps approve hidden", async () => {
    const user = userEvent.setup();
    renderAt("/reviews/REV-001");
    const body = await screen.findByLabelText(/^body$/i);
    await user.type(body, " Pay or face legal action.");
    await user.click(screen.getByRole("button", { name: /save edit and re-validate/i }));
    expect(await screen.findByText(/re-validated revision 2/i)).toBeInTheDocument();
    await waitFor(() => expect(approveButton()).toBeNull());
    expect(screen.getByRole("list", { name: /validation findings/i })).toHaveTextContent(
      "blocked_term",
    );
  });

  it("requires a reason before rejecting", async () => {
    const user = userEvent.setup();
    renderAt("/reviews/REV-001");
    await screen.findByTestId("draft-subject");
    const reject = screen.getByRole("button", { name: /^reject$/i });
    expect(reject).toBeDisabled();
    await user.type(screen.getByLabelText(/reason \(required\)/i), "   ");
    expect(reject).toBeDisabled();
    await user.type(screen.getByLabelText(/reason \(required\)/i), "Tone too pushy");
    expect(reject).toBeEnabled();
    await user.click(reject);
    await waitFor(() => expect(screen.getAllByText("rejected").length).toBeGreaterThan(0));
    expect(screen.getByText(/tone too pushy/i)).toBeInTheDocument();
    expect(approveButton()).toBeNull();
  });

  it("shows review_not_found for an unknown review", async () => {
    renderAt("/reviews/REV-999");
    expect(await screen.findByRole("alert")).toHaveTextContent("review_not_found");
  });
});
