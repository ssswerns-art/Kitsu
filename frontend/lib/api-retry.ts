/**
 * API Retry Policy
 * 
 * This module provides retry logic with exponential backoff for API calls.
 * 
 * Policies:
 * - INTERNAL_API: retry=0 (fail fast for Kitsu backend)
 * - EXTERNAL_API: retry=2, exponential backoff (200ms, 600ms) for third-party APIs
 * 
 * Retry only occurs for retryable errors (BaseApiError.retryable === true)
 */

import { BaseApiError, normalizeToApiError } from "./api-errors";

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
 * Kitsu backend is expected to be stable and return meaningful errors immediately
 */
export const INTERNAL_API_POLICY: RetryPolicy = {
  maxRetries: 0,
  baseDelay: 0,
  backoffMultiplier: 1,
};

/**
 * External API policy: retry with exponential backoff
 * Third-party APIs may be flaky, so retry is beneficial
 * Delays: 200ms, 600ms (200 * 3^1)
 */
export const EXTERNAL_API_POLICY: RetryPolicy = {
  maxRetries: 2,
  baseDelay: 200,
  backoffMultiplier: 3,
};

/**
 * Sleep utility for retry delays
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Wraps an async function with retry logic
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
 * This is for external APIs where we want graceful degradation
 * 
 * @param fn - The async function to execute
 * @param policy - The retry policy to use
 * @param endpoint - The API endpoint being called (for error normalization)
 * @param fallback - The fallback value to return if all retries fail
 * @returns Promise with the result of fn, or fallback if all retries fail
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
  try {
    return await withRetry(fn, policy, endpoint);
  } catch (error) {
    // After all retries exhausted, return fallback
    // Only for external APIs - internal APIs should fail fast
    const apiError = error instanceof BaseApiError ? error : normalizeToApiError(error, endpoint);
    
    if (apiError.source === "external") {
      // Log the error for debugging but return fallback
      // eslint-disable-next-line no-console
      console.warn(`External API ${endpoint} failed after retries, using fallback:`, apiError.message);
      return fallback;
    }
    
    // Internal API errors should not use fallback - rethrow
    throw apiError;
  }
}
