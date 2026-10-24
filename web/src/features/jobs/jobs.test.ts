import { describe, expect, it } from "vitest";
import { markIssues } from "./marks";

describe("AGG marks", () => {
  it("cuts the text around each quoted problem, case-insensitively and without overlaps", () => {
    const text = "Für unser junges Team. Deutsch als Muttersprache. Bitte mit Foto.";
    const pieces = markIssues(text, [
      { rule: "age", severity: "block", quote: "junges Team", advice: "" },
      { rule: "origin-native-language", severity: "block", quote: "muttersprache", advice: "" },
      { rule: "photo", severity: "warn", quote: "mit Foto", advice: "" },
      { rule: "gender-title", severity: "warn", quote: "nicht im Text", advice: "" },
    ]);
    expect(pieces.map((p) => p.text).join("")).toBe(text);
    expect(pieces.filter((p) => p.issue).map((p) => p.text)).toEqual(["junges Team", "Muttersprache", "mit Foto"]);
  });
});
