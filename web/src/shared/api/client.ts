/** The one place that talks HTTP. Every call carries the API key; errors become ApiError. */

const KEY = "fkp.apiKey";

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

export const apiKey = {
  get(): string {
    try {
      return sessionStorage.getItem(KEY) ?? "";
    } catch {
      return memory;
    }
  },
  set(v: string) {
    memory = v;
    try {
      sessionStorage.setItem(KEY, v);
    } catch {
      /* private mode: the in-memory copy is enough for this tab */
    }
  },
  clear() {
    memory = "";
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      /* nothing stored */
    }
  },
};
let memory = "";

function messageOf(status: number, detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  if (status === 401) return "The access key was not accepted.";
  if (status === 403) return "Your role does not allow this.";
  if (status >= 500) return "The server could not answer. Try again in a moment.";
  return `Request failed (${status}).`;
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${apiKey.get()}`);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers, body });
  } catch {
    throw new ApiError(0, "No connection to the server. Check your network and try again.");
  }
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? (data as { detail: unknown }).detail : data;
    throw new ApiError(res.status, messageOf(res.status, detail), detail);
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
