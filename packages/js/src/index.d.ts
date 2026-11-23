export const VERSION: string;

export interface RateLimitBucketState {
  name: string;
  unit: string;
  limit: number | null;
  remaining: number | null;
  used: number | null;
  resetAfterMs: number | null;
  resetAt: string | null;
}

export interface RateLimitResult {
  provider: string | null;
  isLimited: boolean;
  limit: number | null;
  remaining: number | null;
  resetAfterMs: number | null;
  resetAt: string | null;
  retryAfterMs: number | null;
  strategy: "honor_retry_after" | "wait_until_reset" | "exponential_backoff_jitter";
  buckets: Record<string, RateLimitBucketState>;
}

export interface BackoffOptions {
  baseMs?: number;
  maxMs?: number;
  jitter?: "full" | "equal" | "none";
  rng?: () => number;
}

export interface FetchWithRateLimitOptions {
  provider?: string | null;
  maxRetries?: number;
  maxWaitMs?: number;
  fetchImpl?: typeof fetch;
  sleepImpl?: (ms: number) => Promise<void>;
  rng?: () => number;
}

export function listProviders(): string[];
export function getProvider(id: string): Record<string, unknown> | null;
export function detectProvider(headers: Headers | Record<string, string | undefined>): string | null;
export function parseHttpHeadersText(rawText: string): { status: number; headers: Record<string, string> };
export function computeBackoffMs(attempt: number, options?: BackoffOptions): number;
export function parseRateLimit(
  provider: string | null,
  headers: Headers | Record<string, string | undefined>,
  status?: number,
  nowMs?: number
): RateLimitResult;

export class RateLimitTracker {
  constructor(clockMs?: () => number);
  update(
    provider: string | null,
    headers: Headers | Record<string, string | undefined>,
    status?: number,
    key?: string | null
  ): RateLimitResult;
  getDelayMs(key: string, options?: { minRemaining?: number }): number;
  clear(key?: string | null): void;
  snapshot(): Record<string, RateLimitResult>;
}

export function fetchWithRateLimit(
  url: string | URL,
  init?: RequestInit,
  options?: FetchWithRateLimitOptions
): Promise<{ response: Response; rateLimit: RateLimitResult }>;
