/**
 * Error Boundary Policy — Strict Error Handling Contract
 * ========================================================
 * 
 * This module defines the strict policy for error boundary behavior.
 * 
 * ARCHITECTURAL INVARIANTS (enforced at runtime):
 * 
 * 1. ERROR CLASSIFICATION
 *    - ApiContractError → CRASH (developer error)
 *    - Internal API error → CRASH (backend issue must be visible)
 *    - External API error → CONTROLLED DEGRADATION (graceful fallback)
 * 
 * 2. UI ISOLATION
 *    - UI components DO NOT make error handling decisions
 *    - ALL error handling decisions are made by this policy
 *    - Error boundaries delegate to this policy module
 * 
 * 3. DETERMINISTIC BEHAVIOR
 *    - Same error type ALWAYS produces same handling strategy
 *    - No conditional logic in UI based on error
 *    - Policy is single source of truth
 * 
 * 4. FALLBACK PHILOSOPHY
 *    - App shell NEVER crashes from external API errors
 *    - Internal errors ALWAYS crash (fail-fast principle)
 *    - Contract violations ALWAYS crash (developer visibility)
 * 
 * ERROR HANDLING STRATEGIES:
 * - CRASH: Show error boundary UI, allow recovery
 * - DEGRADE: Log error, show partial UI, continue operation
 * - IGNORE: Log only (for non-critical errors)
 */

import {
  BaseApiError,
  ApiContractError,
} from "./api-errors";

/**
 * Error handling strategy discriminated union
 */
export type ErrorHandlingStrategy =
  | { type: "crash"; reason: string }
  | { type: "degrade"; reason: string; fallbackMessage?: string }
  | { type: "ignore"; reason: string };

/**
 * Determine if error should trigger error boundary
 * 
 * POLICY:
 * - ApiContractError → true (CRASH - developer must see contract violations)
 * - Internal API error → true (CRASH - backend issues must be visible)
 * - External API error → false (DEGRADE - graceful degradation)
 * - Unknown errors → true (CRASH - safety first)
 * 
 * INVARIANT:
 * UI does NOT call this directly. Error boundary calls this.
 * UI never makes error handling decisions.
 * 
 * @param error - Error that occurred
 * @returns true if error boundary should activate, false for graceful degradation
 * 
 * @example
 * // In error boundary component
 * const useErrorBoundary = (error: Error) => {
 *   return shouldUseErrorBoundary(error);
 * };
 */
export function shouldUseErrorBoundary(error: Error | unknown): boolean {
  // Contract violations always crash
  if (error instanceof ApiContractError) {
    return true;
  }
  
  // All internal API errors crash (fail-fast)
  if (error instanceof BaseApiError && error.source === "internal") {
    return true;
  }
  
  // External API errors degrade gracefully
  if (error instanceof BaseApiError && error.source === "external") {
    return false;
  }
  
  // Unknown errors crash for safety
  return true;
}

/**
 * Get error handling strategy for a given error
 * 
 * POLICY DECISIONS:
 * 1. ApiContractError → CRASH
 *    - Reason: Contract violations are developer errors
 *    - Must be visible in development and production
 *    - Cannot be masked by fallbacks
 * 
 * 2. Internal API error → CRASH
 *    - Reason: Internal API failures indicate backend issues
 *    - Must be visible to operators
 *    - Fallbacks would mask critical problems
 * 
 * 3. External API error → DEGRADE
 *    - Reason: External APIs are unreliable
 *    - App should continue functioning
 *    - Log error for monitoring
 * 
 * 4. Unknown error → CRASH
 *    - Reason: Safety first
 *    - Unknown errors might be critical
 *    - Better to crash than silently fail
 * 
 * @param error - Error that occurred
 * @returns ErrorHandlingStrategy with type and reason
 * 
 * @example
 * const strategy = getErrorHandlingStrategy(error);
 * if (strategy.type === "crash") {
 *   // Show error boundary UI
 * } else if (strategy.type === "degrade") {
 *   // Show partial UI with fallback
 * }
 */
export function getErrorHandlingStrategy(
  error: Error | unknown
): ErrorHandlingStrategy {
  // POLICY: Contract violations always crash
  if (error instanceof ApiContractError) {
    return {
      type: "crash",
      reason:
        "Contract violation detected. " +
        `Endpoint: ${error.endpoint}. ` +
        `Contract Error: ${error.contractError.message}. ` +
        "This is a developer error that must be fixed.",
    };
  }
  
  // POLICY: Internal API errors always crash
  if (error instanceof BaseApiError && error.source === "internal") {
    return {
      type: "crash",
      reason:
        "Internal API error detected. " +
        `Endpoint: ${error.endpoint}. ` +
        `Error: ${error.message}. ` +
        "Internal APIs must be stable. This indicates a backend issue.",
    };
  }
  
  // POLICY: External API errors degrade gracefully
  if (error instanceof BaseApiError && error.source === "external") {
    return {
      type: "degrade",
      reason:
        "External API error detected. " +
        `Endpoint: ${error.endpoint}. ` +
        `Error: ${error.message}. ` +
        "Continuing with fallback data.",
      fallbackMessage: "Some content may be unavailable due to external service issues.",
    };
  }
  
  // POLICY: Unknown errors crash for safety
  const message = error instanceof Error ? error.message : String(error);
  return {
    type: "crash",
    reason:
      "Unknown error type detected. " +
      `Error: ${message}. ` +
      "Crashing for safety. Unknown errors might be critical.",
  };
}

/**
 * Assert that error handling is not done in UI
 * 
 * INVARIANT:
 * - UI components MUST NOT have try/catch for error handling
 * - UI components MUST NOT call getErrorHandlingStrategy
 * - Only error boundaries and query layer may use this policy
 * 
 * @param callerLocation - Location of caller (e.g., file path)
 * @throws Error if called from UI component
 */
export function assertErrorHandlingInPolicy(callerLocation: string): void {
  const uiPatterns = [
    /\/components\//,
    /\/app\/.*\.tsx$/,
    /\/ui\//,
  ];
  
  const isUIComponent = uiPatterns.some(pattern => pattern.test(callerLocation));
  
  if (isUIComponent) {
    throw new Error(
      `INVARIANT VIOLATION: Error handling policy called from UI component: ${callerLocation}. ` +
      `UI components MUST NOT make error handling decisions. ` +
      `Only error boundaries and query layer may use error handling policy.`
    );
  }
}

/**
 * Log error according to policy
 * 
 * BEHAVIOR:
 * - Crash errors: console.error (visible in production)
 * - Degrade errors: console.warn (monitoring)
 * - Ignore errors: console.debug (development only)
 * 
 * @param error - Error that occurred
 * @param strategy - Handling strategy from getErrorHandlingStrategy
 */
export function logErrorByPolicy(
  error: Error | unknown,
  strategy: ErrorHandlingStrategy
): void {
  const logMessage = `[Error Policy] ${strategy.type.toUpperCase()}: ${strategy.reason}`;
  
  if (strategy.type === "crash") {
    // eslint-disable-next-line no-console
    console.error(logMessage, error);
  } else if (strategy.type === "degrade") {
    // eslint-disable-next-line no-console
    console.warn(logMessage, error);
  } else {
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.debug(logMessage, error);
    }
  }
}

/**
 * Check if error allows app shell to continue
 * 
 * POLICY:
 * - External API errors: YES (app shell continues)
 * - Internal API errors: NO (app shell crashes)
 * - Contract errors: NO (app shell crashes)
 * - Unknown errors: NO (app shell crashes)
 * 
 * @param error - Error that occurred
 * @returns true if app shell can continue, false if it must crash
 * 
 * @example
 * if (canAppShellContinue(error)) {
 *   // Show partial UI with fallback
 * } else {
 *   // Show error boundary
 * }
 */
export function canAppShellContinue(error: Error | unknown): boolean {
  const strategy = getErrorHandlingStrategy(error);
  return strategy.type === "degrade" || strategy.type === "ignore";
}

/**
 * Get user-friendly error message for error boundary
 * 
 * POLICY:
 * - Contract errors: Technical message for developers
 * - Internal errors: Generic message (don't expose internals)
 * - External errors: Specific message about external service
 * - Unknown errors: Generic message
 * 
 * @param error - Error that occurred
 * @returns User-friendly error message
 */
export function getUserFriendlyErrorMessage(error: Error | unknown): string {
  if (error instanceof ApiContractError) {
    // Show technical details in development
    if (process.env.NODE_ENV !== "production") {
      return `Developer Error: Contract violation at ${error.endpoint}. ${error.contractError.message}`;
    }
    return "A technical error occurred. Please try again or contact support.";
  }
  
  if (error instanceof BaseApiError) {
    if (error.source === "internal") {
      return "An error occurred while loading content. Please try again.";
    }
    // External API error
    return "Some content is temporarily unavailable. The app will continue to work.";
  }
  
  return "An unexpected error occurred. Please try again.";
}
