import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SandboxPage } from "./SandboxPage";

afterEach(() => vi.unstubAllGlobals());

const page = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><SandboxPage /></QueryClientProvider>);

describe("sandbox chat", () => {
  it("starts empty, sends a message and shows the reply buttons", async () => {
    const transcript = [
      { direction: "in", kind: "text", body: "Hallo", purpose: null, at: "2026-10-24T10:00:00Z", buttons: [] },
      { direction: "out", kind: "buttons", body: "Bist du einverstanden?", purpose: "intro", at: "2026-10-24T10:00:01Z",
        buttons: [{ id: "consent_yes", title: "Ja" }, { id: "consent_no", title: "Nein" }] },
    ];
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ transcript }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    page();
    expect(await screen.findByText("Starte das Gespräch")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Nachricht schreiben"), "Hallo");
    await userEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(await screen.findByText("Bist du einverstanden?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ja" })).toBeInTheDocument();
    expect(JSON.parse(String((fetch.mock.calls[1]![1] as RequestInit).body))).toMatchObject({ text: "Hallo" });
  });

  it("explains when the sandbox is switched off on the server", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "sandbox is off" }), { status: 404 })));
    page();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("FKP_SANDBOX=1"));
  });
});
