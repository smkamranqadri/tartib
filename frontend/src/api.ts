export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export class Unauthorized extends ApiError {
  constructor() {
    super(401, "not logged in");
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    credentials: "same-origin",
  });
  if (res.status === 401) {
    onUnauthorized();
    throw new Unauthorized();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, String(detail));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const login = (password: string) => post<{ ok: true }>("/api/login", { password });
export const logout = () => post<{ ok: true }>("/api/logout");
export const capture = (text: string) => post<{ id: number }>("/api/capture", { text });
