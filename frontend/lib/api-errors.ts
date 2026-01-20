/**
 * Unified API Error Model
 * 
 * This module provides a unified error hierarchy for all API interactions.
 * All errors extend BaseApiError and provide:
 * - source: "internal" | "external" - distinguishes Kitsu backend vs third-party APIs
 * - endpoint: string - the API endpoint that failed
 * - retryable: boolean - whether the error should trigger retry logic
 * 
 * Error hierarchy:
 * - ApiNetworkError: Network-level failures (ECONNABORTED, no response)
 * - ApiTimeoutError: Request timeouts
 * - ApiRateLimitError: Rate limit errors (429)
 * - ApiContractError: Contract violations (wrapper for ContractError)
 * - ApiExternalUnavailableError: External API unavailable (5xx)
 */

import { ContractError } from "./contract-guards";

export type ApiSource = "internal" | "external";

/**
 * Base class for all API errors
 * All API errors must extend this class
 */
export abstract class BaseApiError extends Error {
  public readonly source: ApiSource;
  public readonly endpoint: string;
  public readonly retryable: boolean;
  public readonly originalError?: Error;

  constructor(
    message: string,
    source: ApiSource,
    endpoint: string,
    retryable: boolean,
    originalError?: Error
  ) {
    super(message);
    this.name = this.constructor.name;
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
 * Always retryable for external APIs
 */
export class ApiNetworkError extends BaseApiError {
  constructor(
    source: ApiSource,
    endpoint: string,
    originalError?: Error
  ) {
    super(
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
 * Always retryable for external APIs
 */
export class ApiTimeoutError extends BaseApiError {
  constructor(
    source: ApiSource,
    endpoint: string,
    originalError?: Error
  ) {
    super(
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
 * Never retryable (need to back off longer than our retry window)
 */
export class ApiRateLimitError extends BaseApiError {
  constructor(
    source: ApiSource,
    endpoint: string,
    originalError?: Error
  ) {
    super(
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
 * Never retryable (contract won't fix itself on retry)
 * Wraps ContractError from contract-guards
 */
export class ApiContractError extends BaseApiError {
  public readonly contractError: ContractError;

  constructor(
    source: ApiSource,
    endpoint: string,
    contractError: ContractError
  ) {
    super(
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
 * Always retryable for external APIs
 */
export class ApiExternalUnavailableError extends BaseApiError {
  public readonly status: number;

  constructor(
    endpoint: string,
    status: number,
    originalError?: Error
  ) {
    super(
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
 * This is the main entry point for error normalization
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
