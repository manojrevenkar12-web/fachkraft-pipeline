import type { FieldValue, Message } from "../../shared/api/types";

export interface Span { index: number; start: number; end: number }

/**
 * Where a fact came from: the message it was read from and the quoted span inside it. The
 * stored message is the redacted one, so a span that no longer occurs (it sat in a removed
 * health sentence) is not shown rather than guessed.
 */
export function locate(messages: Message[], fv: FieldValue): Span | null {
  const quote = fv.evidence.trim();
  if (!quote) return null;
  // whole words first, exact case first: the licence "B" is not the B of "Berlin"
  const esc = quote.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const patterns = [new RegExp(`(?<![\\p{L}\\p{N}])${esc}(?![\\p{L}\\p{N}])`, "u"), new RegExp(`(?<![\\p{L}\\p{N}])${esc}(?![\\p{L}\\p{N}])`, "iu")];
  const find = (i: number): Span | null => {
    const m = messages[i];
    if (!m || m.direction !== "in") return null;
    for (const re of patterns) {
      const hit = re.exec(m.body);
      if (hit) return { index: i, start: hit.index, end: hit.index + hit[0].length };
    }
    const at = m.body.toLowerCase().indexOf(quote.toLowerCase());
    return at >= 0 ? { index: i, start: at, end: at + quote.length } : null;
  };
  const own = messages.findIndex((m) => m.direction === "in" && m.channel_id === fv.message_id);
  if (own >= 0) {
    const s = find(own);
    if (s) return s;
  }
  for (let i = messages.length - 1; i >= 0; i--) {
    const s = find(i);
    if (s) return s;
  }
  return null;
}

/** Split a message body around one span, for rendering a highlight. */
export function splitAt(body: string, span: { start: number; end: number } | null): [string, string, string] {
  if (!span) return [body, "", ""];
  return [body.slice(0, span.start), body.slice(span.start, span.end), body.slice(span.end)];
}
