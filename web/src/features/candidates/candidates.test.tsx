import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { CandidateRow, FieldValue, Message } from "../../shared/api/types";
import { CandidateList, relativeTime } from "./CandidateList";
import { locate, splitAt } from "./evidence";
import { groupCandidates } from "./groups";

const row = (over: Partial<CandidateRow>): CandidateRow => ({
  id: "c1", channel: "whatsapp", stage: "collecting", lang: "de", job_id: null, name: "Lea Hoffmann", occupation: ["koch"],
  place: "Köln", updated_at: "2026-10-24T10:00:00Z", created_at: "2026-10-24T09:00:00Z", matches: [], fields: 3, ...over,
});
const msg = (body: string, over: Partial<Message> = {}): Message => ({
  direction: "in", kind: "text", channel_id: "m1", body, purpose: null, status: null, category: null, cost: 0, at: "2026-10-24T10:00:00Z",
  redacted: false, ...over,
});
const fv = (evidence: string, message_id = "m1"): FieldValue => ({ value: "x", evidence, message_id, source: "rules", confidence: 1, at: "" });

function renderList(props: Partial<Parameters<typeof CandidateList>[0]>) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}><MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <CandidateList rows={undefined} loading={false} error={null} onRetry={() => {}} onSandbox={() => {}} {...props} />
    </MemoryRouter></QueryClientProvider>,
  );
}

describe("candidate list", () => {
  it("shows skeletons while loading", () => {
    renderList({ loading: true });
    expect(screen.getAllByTestId("skeleton").length).toBeGreaterThan(3);
  });

  it("shows the error with a retry that calls back", async () => {
    const onRetry = vi.fn();
    renderList({ error: new Error("Der Server antwortet nicht."), onRetry });
    expect(screen.getByRole("alert")).toHaveTextContent("Der Server antwortet nicht.");
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("invites to the sandbox when nobody has written yet", async () => {
    const onSandbox = vi.fn();
    renderList({ rows: [], onSandbox });
    expect(screen.getByText("Noch keine Bewerbungen")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Chat testen" }));
    expect(onSandbox).toHaveBeenCalled();
  });

  it("puts people handed over first and filters by search", async () => {
    renderList({ rows: [row({ id: "a", name: "Ali Kaya" }), row({ id: "b", name: "Jonas Becker", stage: "handed_over", matches: [{ job_id: "J-1", verdict: "fit" }] })] });
    const groups = screen.getAllByRole("region");
    expect(groups[0]).toHaveAccessibleName("Bereit für dich");
    await userEvent.type(screen.getByRole("searchbox"), "ali");
    expect(screen.queryByText("Jonas Becker")).not.toBeInTheDocument();
    expect(screen.getByText("Ali Kaya")).toBeInTheDocument();
  });
});

describe("grouping and time", () => {
  it("orders groups by work to do and rows by recency", () => {
    const g = groupCandidates([row({ id: "1", stage: "pooled" }), row({ id: "2", stage: "human" }), row({ id: "3", stage: "handed_over", updated_at: "2026-10-23T00:00:00Z" }),
      row({ id: "4", stage: "handed_over", updated_at: "2026-10-24T00:00:00Z" })]);
    expect(g.map((x) => x.id)).toEqual(["ready", "person", "pool"]);
    expect(g[0]!.rows.map((r) => r.id)).toEqual(["4", "3"]);
  });

  it("says how long ago in German", () => {
    const now = Date.parse("2026-10-24T12:00:00Z");
    expect(relativeTime("2026-10-24T11:30:00Z", now)).toBe("vor 30 Min.");
    expect(relativeTime("2026-10-23T12:00:00Z", now)).toBe("gestern");
  });
});

describe("evidence", () => {
  it("finds the quote as a whole word in its own message, not inside another word", () => {
    const messages = [msg("Wohne in Berlin, Führerschein B", { channel_id: "m1" })];
    const span = locate(messages, fv("B"))!;
    expect(messages[0]!.body.slice(span.start, span.end)).toBe("B");
    expect(span.start).toBe(messages[0]!.body.length - 1);
  });

  it("falls back to the latest message that holds the quote, and gives up when redacted away", () => {
    const messages = [msg("ich bin Koch", { channel_id: "a" }), msg("seit 5 Jahren", { channel_id: "b" })];
    expect(locate(messages, fv("seit 5 Jahren", "zzz"))?.index).toBe(1);
    expect(locate(messages, fv("Rückenprobleme"))).toBeNull();
  });

  it("splits a body around a span", () => {
    expect(splitAt("abc def", { start: 4, end: 7 })).toEqual(["abc ", "def", ""]);
    expect(splitAt("abc", null)).toEqual(["abc", "", ""]);
  });
});
