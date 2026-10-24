import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, apiKey } from "./api/client";
import { checkDetail, formatValue, messageText } from "./text/de";
import { Verdict } from "./ui/Verdict";

afterEach(() => { vi.unstubAllGlobals(); apiKey.clear(); });

describe("api client", () => {
  it("sends the key and returns JSON", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify([{ id: 1 }]), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    apiKey.set("k".repeat(20));
    await expect(api("/api/jobs")).resolves.toEqual([{ id: 1 }]);
    expect((fetch.mock.calls[0]![1] as RequestInit).headers).toBeInstanceOf(Headers);
    expect(((fetch.mock.calls[0]![1] as RequestInit).headers as Headers).get("Authorization")).toBe(`Bearer ${"k".repeat(20)}`);
  });

  it("turns server errors into readable ApiErrors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "the 24-hour window is closed" }), { status: 409 })));
    await expect(api("/x")).rejects.toMatchObject({ status: 409, message: "the 24-hour window is closed" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const e = await api("/x").catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect((e as ApiError).status).toBe(0);
  });
});

describe("text", () => {
  it("formats profile values for recruiters", () => {
    expect(formatValue("shifts", { early: true, late: true, night: false })).toBe("früh, spät; nicht nachts");
    expect(formatValue("licences", [])).toBe("keine");
    expect(formatValue("licences", ["CE", "code95"])).toBe("CE, Code 95");
    expect(formatValue("location", { plz: "04109", place: "Leipzig" })).toBe("04109 Leipzig");
    expect(formatValue("occupation", ["berufskraftfahrer"])).toBe("Berufskraftfahrer/in");
  });

  it("puts match explanations into German", () => {
    expect(checkDetail("B1 (needs A2)")).toBe("B1 (verlangt A2)");
    expect(checkDetail("starts 2027-02-15, 15 days after 2027-01-31")).toBe("Start 15.02.2027, 15 Tage nach 31.01.2027");
    expect(checkDetail("early, late")).toBe("früh, spät");
    expect(checkDetail("missing code95")).toBe("fehlt: Code 95");
  });

  it("shows a tapped button by its label", () => {
    expect(messageText("[consent_yes]")).toBe("↩ Ja, los geht's");
    expect(messageText("[x] und Text")).toBe("[x] und Text");
  });
});

describe("verdict", () => {
  it("never relies on colour alone: the label is always there", () => {
    render(<Verdict verdict="near" />);
    expect(screen.getByText("fast")).toBeInTheDocument();
  });
});
