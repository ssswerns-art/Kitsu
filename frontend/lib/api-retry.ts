/**
 * API Retry Policy — ENFORCED INVARIANTS
 * ========================================
 * 
 * This module provides retry logic with exponential backoff for API calls.
 * 
 * RETRY PHILOSOPHY:
 * 
 * 1. INTERNAL APIs (Kitsu backend):
 *    - Fail-fast: maxRetries MUST be 0
 *    - No retry overhead for stable backend
 *    - Errors propagate immediately to error boundary
 *    - NEVER use fallback (must surface errors)
 * 
 * 2. EXTERNAL APIs (third-party):
 *    - Retry with exponential backoff
 *    - maxRetries MUST be > 0
 *    - Only retry transient failures (retryable=true)
 *    - MAY use fallback for graceful degradation
 * 
 * 3. CONTRACT VIOLATIONS:
 *    - NEVER retryable (contract won't fix itself)
 *    - NEVER use fallback (must surface to developers)
 *    - Always fail-fast regardless of API source
 * 
 * ARCHITECTURAL INVARIANTS (enforced at runtime):
 * 
 * - INTERNAL_API_POLICY.maxRetries MUST equal 0
 * - EXTERNAL_API_POLICY.maxRetries MUST be > 0
 * - withRetryAndFallback MUST reject internal API sources
 * - Fallback MUST NOT mask contract errors
 * 
 * POLICIES:
 * - INTERNAL_API_POLICY: maxRetries=0 (fail-fast)
 * - EXTERNAL_API_POLICY: maxRetries=2, exponential backoff (200ms, 600ms)
 */

import { BaseApiError, normalizeToApiError, ApiContractError, getApiSource } from "./api-errors";

/**
 * Retry policy configuration
 */
export type RetryPolicy = {
  /** Maximum number of retry attempts (0 = no retry) */
  maxRetries: number;
  /** Base delay in milliseconds for exponential backoff */
  baseDelay: number;
  /** Multiplier for exponential backoff */
  backoffMultiplier: number;
};

/**
 * Internal API policy: fail fast, no retries
 * 
 * INVARIANT: maxRetries MUST be 0
 * This is enforced at runtime in assertInternalApiPolicy()
 */
export const INTERNAL_API_POLICY: RetryPolicy = {
  maxRetries: 0,
  baseDelay: 0,
  backoffMultiplier: 1,
};

/**
 * External API policy: retry with exponential backoff
 * 
 * INVARIANT: maxRetries MUST be > 0
 * This is enforced at runtime in assertExternalApiPolicy()
 * 
 * Delays: 200ms, 600ms (200 * 3^1)
 */
export const EXTERNAL_API_POLICY: RetryPolicy = {
  maxRetries: 2,
  baseDelay: 200,
  backoffMultiplier: 3,
};

/**
 * Runtime assertion: INTERNAL_API_POLICY.maxRetries === 0
 * 
 * RATIONALE:
 * Internal APIs must fail-fast. Retry would add latency without benefit.
 * If this assertion fails, INTERNAL_API_POLICY was incorrectly modified.
 */
function assertInternalApiPolicy(policy: RetryPolicy): void {
  if (policy.maxRetries !== 0) {
    throw new Error(
      `INVARIANT VIOLATION: Internal API policy must have maxRetries=0, got ${policy.maxRetries}. ` +
      `Internal APIs must fail-fast without retry.`
    );
  }
}

/**
 * Runtime assertion: EXTERNAL_API_POLICY.maxRetries > 0
 * 
 * RATIONALE:
 * External APIs should retry transient failures. No retry defeats the purpose.
 * If this assertion fails, EXTERNAL_API_POLICY was incorrectly modified.
 */
function assertExternalApiPolicy(policy: RetryPolicy): void {
  if (policy.maxRetries <= 0) {
    throw new Error(
      `INVARIANT VIOLATION: External API policy must have maxRetries > 0, got ${policy.maxRetries}. ` +
      `External APIs should retry transient failures.`
    );
  }
}

/**
 * Sleep utility for retry delays
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Wraps an async function with retry logic
 * 
 * RETRY BEHAVIOR:
 * - Only retries errors with retryable=true
 * - Respects policy.maxRetries
 * - Uses exponential backoff
 * 
 * @param fn - The async function to execute
 * @param policy - The retry policy to use
 * @param endpoint - The API endpoint being called (for error normalization)
 * @returns Promise with the result of fn, or throws BaseApiError after exhausting retries
 * 
 * @example
 * // External API with retry
 * const data = await withRetry(
 *   () => api.get("/api/schedule"),
 *   EXTERNAL_API_POLICY,
 *   "/api/schedule"
 * );
 * 
 * @example
 * // Internal API without retry
 * const data = await withRetry(
 *   () => api.get("/anime"),
 *   INTERNAL_API_POLICY,
 *   "/anime"
 * );
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  policy: RetryPolicy,
  endpoint: string
): Promise<T> {
  let lastError: BaseApiError | undefined;

  // Initial attempt + retries
  const totalAttempts = 1 + policy.maxRetries;

  for (let attempt = 0; attempt < totalAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      // Normalize to our error hierarchy
      const apiError = normalizeToApiError(error, endpoint);
      lastError = apiError;

      // Check if we should retry
      const isLastAttempt = attempt === totalAttempts - 1;
      
      if (isLastAttempt || !apiError.retryable) {
        // No more retries or error is not retryable
        throw apiError;
      }

      // Calculate exponential backoff delay
      // First retry: baseDelay * backoffMultiplier^0 = baseDelay
      // Second retry: baseDelay * backoffMultiplier^1 = baseDelay * backoffMultiplier
      const delay = policy.baseDelay * Math.pow(policy.backoffMultiplier, attempt);
      
      await sleep(delay);
      // Continue to next attempt
    }
  }

  // Should never reach here, but TypeScript needs this
  throw lastError || new Error("Unexpected retry loop exit");
}

/**
 * Wraps an async function with retry logic and provides a fallback value on failure
 * 
 * FALLBACK GUARANTEE (enforced at runtime):
 * - Fallbacks are ONLY for external APIs
 * - Internal APIs MUST fail-fast (no fallback)
 * - Contract errors NEVER use fallback (must surface)
 * 
 * INVARIANTS:
 * 1. If endpoint is internal API → throw immediately (no fallback)
 * 2. If error is ApiContractError → rethrow (no fallback)
 * 3. Policy MUST be EXTERNAL_API_POLICY or equivalent
 * 
 * @param fn - The async function to execute
 * @param policy - The retry policy to use (MUST have maxRetries > 0)
 * @param endpoint - The API endpoint being called
 * @param fallback - The fallback value (used ONLY for external APIs)
 * @returns Promise with the result of fn, or fallback if all retries fail
 * 
 * @throws Error if called with internal API endpoint
 * @throws ApiContractError if contract violation occurs (never masked)
 * 
 * @example
 * // External API with controlled fallback
 * const schedule = await withRetryAndFallback(
 *   () => api.get("/api/schedule"),
 *   EXTERNAL_API_POLICY,
 *   "/api/schedule",
 *   { data: [] }
 * );
 */
export async function withRetryAndFallback<T>(
  fn: () => Promise<T>,
  policy: RetryPolicy,
  endpoint: string,
  fallback: T
): Promise<T> {
  // INVARIANT: withRetryAndFallback is ONLY for external APIs
  const source = getApiSource(endpoint);
  if (source === "internal") {
    throw new Error(
      `INVARIANT VIOLATION: withRetryAndFallback called with internal API endpoint: ${endpoint}. ` +
      `Internal APIs MUST use withRetry() without fallback. ` +
      `Fallbacks mask errors and violate fail-fast principle.`
    );
  }

  // INVARIANT: Policy must allow retries for external APIs
  assertExternalApiPolicy(policy);

  try {
    return await withRetry(fn, policy, endpoint);
  } catch (error) {
    const apiError = error instanceof BaseApiError ? error : normalizeToApiError(error, endpoint);
    
    // INVARIANT: Contract errors are NEVER masked by fallback
    if (apiError instanceof ApiContractError) {
      throw apiError;
    }
    
    // Only external APIs reach this point (enforced above)
    // Log the error for debugging but return fallback
    // eslint-disable-next-line no-console
    console.warn(`External API ${endpoint} failed after retries, using fallback:`, apiError.message);
    return fallback;
  }
}

// ============================================================================
// QUERY LAYER GUARDRAILS
// ============================================================================

/**
 * Type-safe wrapper for external API queries
 * 
 * ENFORCEMENT:
 * - MUST use EXTERNAL_API_POLICY
 * - MUST use withRetryAndFallback (not withRetry)
 * - MUST provide typed fallback
 * 
 * RATIONALE:
 * External APIs should gracefully degrade with fallback data.
 * Using withRetry without fallback defeats the purpose.
 * 
 * @param fn - The async query function
 * @param endpoint - The external API endpoint
 * @param fallback - Typed fallback value for graceful degradation
 * @returns Promise with query result or fallback
 * 
 * @example
 * const schedule = await assertExternalQuery(
 *   () => api.get("/api/schedule"),
 *   "/api/schedule",
 *   { scheduledAnimes: [] }
 * );
 */
export async function assertExternalQuery<T>(
  fn: () => Promise<T>,
  endpoint: string,
  fallback: T
): Promise<T> {
  // Runtime check: endpoint must be external
  const source = getApiSource(endpoint);
  if (source !== "external") {
    throw new Error(
      `GUARDRAIL VIOLATION: assertExternalQuery called with non-external endpoint: ${endpoint}. ` +
      `Use assertInternalQuery for internal APIs.`
    );
  }

  // Enforce policy invariants
  assertExternalApiPolicy(EXTERNAL_API_POLICY);

  return withRetryAndFallback(fn, EXTERNAL_API_POLICY, endpoint, fallback);
}

/**
 * Type-safe wrapper for internal API queries
 * 
 * ENFORCEMENT:
 * - MUST use INTERNAL_API_POLICY
 * - MUST use withRetry (no fallback)
 * - MUST fail-fast on errors
 * 
 * RATIONALE:
 * Internal APIs should fail-fast to surface errors immediately.
 * Fallbacks would mask backend issues and violate fail-fast principle.
 * 
 * @param fn - The async query function
 * @param endpoint - The internal API endpoint
 * @returns Promise with query result
 * @throws BaseApiError on failure (no fallback)
 * 
 * @example
 * const anime = await assertInternalQuery(
 *   () => api.get("/anime"),
 *   "/anime"
 * );
 */
export async function assertInternalQuery<T>(
  fn: () => Promise<T>,
  endpoint: string
): Promise<T> {
  // Runtime check: endpoint must be internal
  const source = getApiSource(endpoint);
  if (source !== "internal") {
    throw new Error(
      `GUARDRAIL VIOLATION: assertInternalQuery called with non-internal endpoint: ${endpoint}. ` +
      `Use assertExternalQuery for external APIs.`
    );
  }

  // Enforce policy invariants
  assertInternalApiPolicy(INTERNAL_API_POLICY);

  return withRetry(fn, INTERNAL_API_POLICY, endpoint);
}
