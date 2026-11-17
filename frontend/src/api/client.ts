// Single HTTP entry point (PLAN.md section 4). Adds X-Demo-User (FR-001), parses the backend error
// body {detail, reasons} into ApiError, and offers an iframe-safe download helper (A-17, 5.5).

export const DEMO_USER_KEY = 'orion.demoUser';
const BASE = '/api/v1';

// The in-memory id is the source of truth; localStorage is a best-effort mirror so login still
// works when storage is blocked (iframe / private mode, spec 5.5). undefined = not loaded yet.
let memoryUserId: string | null | undefined;

/** Current demo user id: memory first, then storage (which can throw, so never trust it). */
export function getStoredUserId(): string | null {
  if (memoryUserId !== undefined) return memoryUserId;
  try {
    memoryUserId = window.localStorage.getItem(DEMO_USER_KEY);
  } catch {
    memoryUserId = null;
  }
  return memoryUserId;
}

export function setStoredUserId(id: string | null): void {
  memoryUserId = id;
  try {
    if (id) window.localStorage.setItem(DEMO_USER_KEY, id);
    else window.localStorage.removeItem(DEMO_USER_KEY);
  } catch {
    /* storage unavailable: the session just will not survive a reload */
  }
}

/** Error raised for every non-2xx response. `reasons` carries the rule/permission reasons. */
export class ApiError extends Error {
  status: number;
  detail: string;
  reasons: string[];

  constructor(status: number, detail: string, reasons: string[] = []) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.reasons = reasons;
  }
}

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  query?: QueryParams;
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: QueryParams): string {
  const url = `${BASE}${path.startsWith('/') ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

function buildHeaders(extra?: Record<string, string>): Headers {
  const headers = new Headers(extra);
  const user = getStoredUserId();
  if (user) headers.set('X-Demo-User', user);
  return headers;
}

async function toApiError(res: Response): Promise<ApiError> {
  let detail = res.statusText || `Request failed (${res.status})`;
  let reasons: string[] = [];
  try {
    const data: unknown = await res.json();
    if (data && typeof data === 'object') {
      const d = data as { detail?: unknown; reasons?: unknown };
      if (typeof d.detail === 'string') detail = d.detail;
      else if (Array.isArray(d.detail)) detail = 'Validation failed'; // FastAPI default 422 shape
      if (Array.isArray(d.reasons)) reasons = d.reasons.map(String);
    }
  } catch {
    /* body was not JSON; keep the status text */
  }
  return new ApiError(res.status, detail, reasons);
}

export async function apiFetch<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const headers = buildHeaders();
  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData; // browser sets the multipart boundary itself
  } else if (opts.body !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(buildUrl(path, opts.query), {
    method: opts.method ?? 'GET',
    headers,
    body,
    signal: opts.signal,
  });
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Authenticated download: fetch -> blob -> temporary <a download>. No window.open (A-17). */
export async function download(path: string, filename: string, query?: QueryParams): Promise<void> {
  const res = await fetch(buildUrl(path, query), { headers: buildHeaders() });
  if (!res.ok) throw await toApiError(res);
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}
