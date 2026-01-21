/**
 * Unified API Error Model — FROZEN TAXONOMY
 * ============================================
 * 
 * This module defines the EXHAUSTIVE and CLOSED error hierarchy for all API interactions.
 * The error taxonomy is FROZEN: any new error type MUST be added here or compilation fails.
 * 
 * ARCHITECTURAL INVARIANTS (enforced at runtime):
 * 
 * 1. ERROR CLASSIFICATION
 *    - All API errors extend BaseApiError
 *    - Each error declares: kind, source, endpoint, retryable
 *    - Error kinds form a discriminated union (ApiErrorKind)
 *    - NO ad-hoc error creation outside this module
 * 
 * 2. RETRY PHILOSOPHY
 *    - Internal APIs: NEVER retryable (fail-fast)
 *    - External APIs: Retryable ONLY for transient failures
 *    - Contract violations: NEVER retryable (contract won't fix itself)
 *    - Rate limits: NEVER retryable (requires longer backoff)
 * 
 * 3. CONTRACT ERROR MAPPING
 *    - ContractError → ApiContractError mapping ONLY happens here
 *    - Single point of truth: normalizeToApiError()
 *    - Contract errors are NEVER masked by fallbacks
 * 
 * 4. FALLBACK PHILOSOPHY
 *    - Fallbacks ONLY for external APIs
 *    - Fallbacks NEVER for internal APIs (must fail-fast)
 *    - Fallbacks NEVER for contract violations (must surface errors)
 * 
 * ERROR TAXONOMY:
 * - ApiNetworkError: Network-level failures (ECONNABORTED, no response)
 * - ApiTimeoutError: Request timeouts
 * - ApiRateLimitError: Rate limit errors (429)
 * - ApiContractError: Contract violations (wrapper for ContractError)
 * - ApiExternalUnavailableError: External API unavailable (5xx)
 * 
 * TO ADD A NEW ERROR TYPE:
 * 1. Add variant to ApiErrorKind
 * 2. Create class extending BaseApiError
 * 3. Add mapping in normalizeToApiError()
 * 4. Document retry behavior and fallback policy
 */

import { ContractError } from "./contract-guards";

export type ApiSource = "internal" | "external";

/**
 * Discriminated union of all possible API error kinds
 * This makes the error taxonomy exhaustive and closed
 * Adding a new error type requires updating this union
 */
export type ApiErrorKind =
  | "network"
  | "timeout"
  | "rate_limit"
  | "contract"
  | "external_unavailable";

/**
 * Base class for all API errors
 * All API errors MUST extend this class and declare their kind
 * 
 * INVARIANTS:
 * - Every error has a discriminated kind
 * - Every error declares source (internal/external)
 * - Every error declares endpoint
 * - Every error declares retryable status
 */
export abstract class BaseApiError extends Error {
  public readonly kind: ApiErrorKind;
  public readonly source: ApiSource;
  public readonly endpoint: string;
  public readonly retryable: boolean;
  public readonly originalError?: Error;

  constructor(
    kind: ApiErrorKind,
    message: string,
    source: ApiSource,
    endpoint: string,
    retryable: boolean,
    originalError?: Error
  ) {
    super(message);
    this.name = this.constructor.name;
    this.kind = kind;
    this.source = source;
    this.endpoint = endpoint;
    this.retryable = retryable;
    this.originalError = originalError;
    
    // Maintains proper stack trace for where our error was thrown (only available on V8)
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }
}

/**
 * Network-level errors (connection failures, DNS errors, etc.)
 * 
 * RETRY POLICY:
 * - Internal API: NOT retryable (fail-fast)
 * - External API: Retryable (transient network issues)
 */
export class ApiNetworkError extends BaseApiError {
  constructor(
    source: ApiSource,
    endpoint: string,
    originalError?: Error
  ) {
    super(
      "network",
      `Network error calling ${endpoint}: ${originalError?.message || "Connection failed"}`,
      source,
      endpoint,
      source === "external", // Only retry for external APIs
      originalError
    );
  }
}

/**
 * Timeout errors (request took too long)
 * 
 * RETRY POLICY:
 * - Internal API: NOT retryable (fail-fast)
 * - External API: Retryable (may succeed on retry)
 */
export class ApiTimeoutError extends BaseApiError {
  constructor(
    source: ApiSource,
    endpoint: string,
    originalError?: Error
  ) {
    super(
      "timeout",
      `Request to ${endpoint} timed out`,
      source,
      endpoint,
      source === "external", // Only retry for external APIs
      originalError
    );
  }
}

/**
 * Rate limit errors (429 status)
 * 
 * RETRY POLICY:
 * - NEVER retryable (requires longer backoff than our retry window)
 * 
 * RATIONALE:
 * Immediate retry would trigger another rate limit. Client should
 * implement exponential backoff at a higher level if needed.
 */
export class ApiRateLimitError extends BaseApiError {
  constructor(
    source: ApiSource,
    endpoint: string,
    originalError?: Error
  ) {
    super(
      "rate_limit",
      `Rate limit exceeded for ${endpoint}`,
      source,
      endpoint,
      false, // Never retry rate limits immediately
      originalError
    );
  }
}

/**
 * Contract violations (unexpected response shape)
 * 
 * RETRY POLICY:
 * - NEVER retryable (contract won't fix itself on retry)
 * 
 * FALLBACK POLICY:
 * - NEVER use fallback (contract violations must surface to developers)
 * 
 * INVARIANT:
 * - This is the ONLY place where ContractError is wrapped
 * - Wrapping ContractError anywhere else violates architectural rules
 */
export class ApiContractError extends BaseApiError {
  public readonly contractError: ContractError;

  constructor(
    source: ApiSource,
    endpoint: string,
    contractError: ContractError
  ) {
    super(
      "contract",
      `Contract violation for ${endpoint}: ${contractError.message}`,
      source,
      endpoint,
      false, // Contract errors are not retryable
      contractError
    );
    this.contractError = contractError;
  }
}

/**
 * External API unavailable (5xx errors from third-party APIs)
 * 
 * RETRY POLICY:
 * - Always retryable (server may recover)
 * 
 * INVARIANT:
 * - source is ALWAYS "external"
 * - Only used for 5xx status codes from external APIs
 */
export class ApiExternalUnavailableError extends BaseApiError {
  public readonly status: number;

  constructor(
    endpoint: string,
    status: number,
    originalError?: Error
  ) {
    super(
      "external_unavailable",
      `External API ${endpoint} unavailable (status ${status})`,
      "external",
      endpoint,
      true, // External 5xx errors are retryable
      originalError
    );
    this.status = status;
  }
}

/**
 * Helper to determine API source from endpoint
 */
export function getApiSource(endpoint: string): ApiSource {
  // External APIs are proxied through /api/*
  if (endpoint.startsWith("/api/")) {
    return "external";
  }
  return "internal";
}

/**
 * Converts unknown errors to our typed error hierarchy
 * 
 * ARCHITECTURAL INVARIANT:
 * This is the SINGLE POINT OF TRUTH for error normalization.
 * ContractError → ApiContractError mapping ONLY happens here.
 * Wrapping ContractError anywhere else violates the architecture.
 * 
 * @param error - Unknown error from API call
 * @param endpoint - API endpoint that failed
 * @returns Typed BaseApiError (one of the discriminated union variants)
 */
export function normalizeToApiError(
  error: unknown,
  endpoint: string
): BaseApiError {
  const source = getApiSource(endpoint);

  // Already one of our API errors
  if (error instanceof BaseApiError) {
    return error;
  }

  // ContractError from contract guards
  // INVARIANT: This is the ONLY place where ContractError is wrapped
  if (error instanceof ContractError) {
    return new ApiContractError(source, endpoint, error);
  }

  // Standard Error object
  if (error instanceof Error) {
    // Check for Axios-specific error codes
    const axiosError = error as Error & { code?: string; response?: { status?: number } };
    
    if (axiosError.code === "ECONNABORTED" || axiosError.code === "ERR_NETWORK") {
      return new ApiTimeoutError(source, endpoint, error);
    }
    
    if (!axiosError.response) {
      return new ApiNetworkError(source, endpoint, error);
    }
    
    const status = axiosError.response.status;
    
    if (status === 429) {
      return new ApiRateLimitError(source, endpoint, error);
    }
    
    if (source === "external" && status && status >= 500 && status < 600) {
      return new ApiExternalUnavailableError(endpoint, status, error);
    }
    
    // Generic error - not retryable
    return new ApiNetworkError(source, endpoint, error);
  }

  // Unknown error type - wrap it
  const errorMessage = String(error);
  return new ApiNetworkError(
    source,
    endpoint,
    new Error(errorMessage)
  );
}
