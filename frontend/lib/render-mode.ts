/**
 * Render Mode Contract — SSR/CSR Lifecycle Guarantees
 * ======================================================
 * 
 * This module enforces explicit declaration of render mode for all pages and layouts.
 * 
 * ARCHITECTURAL INVARIANTS (enforced at runtime):
 * 
 * 1. RENDER MODE DECLARATION
 *    - Every page/layout MUST explicitly declare its render mode
 *    - Mixed mode without contract is FORBIDDEN
 *    - Render mode is determined at module load time
 * 
 * 2. RENDER MODE TYPES
 *    - "server": Server-side rendering only (SSR)
 *    - "client": Client-side rendering only (CSR)
 * 
 * 3. HYDRATION GUARANTEES
 *    - Server mode: Component renders on server first, then hydrates on client
 *    - Client mode: Component only renders on client (use client directive)
 * 
 * 4. DATA FETCHING CONTRACTS
 *    - Server mode: Data can be fetched during SSR, cached for hydration
 *    - Client mode: Data fetched only on client side
 * 
 * USAGE:
 * 
 * @example
 * // In a page component (server-side rendered)
 * export const RENDER_MODE = "server" as const;
 * assertRenderMode(RENDER_MODE);
 * 
 * @example
 * // In a client component
 * "use client";
 * export const RENDER_MODE = "client" as const;
 * assertRenderMode(RENDER_MODE);
 */

/**
 * Discriminated union of supported render modes
 */
export type RenderMode = "server" | "client";

/**
 * Runtime assertion for render mode contract
 * 
 * INVARIANT:
 * - Mode must be one of the valid RenderMode values
 * - This assertion documents the render mode contract
 * 
 * @param mode - The declared render mode
 * @throws Error if mode is invalid
 * 
 * @example
 * const RENDER_MODE = "server" as const;
 * assertRenderMode(RENDER_MODE);
 */
export function assertRenderMode(mode: RenderMode): void {
  if (mode !== "server" && mode !== "client") {
    throw new Error(
      `INVARIANT VIOLATION: Invalid render mode "${mode}". ` +
      `Render mode must be "server" or "client". ` +
      `Every page/layout must explicitly declare its render mode.`
    );
  }
}

/**
 * Detect current render environment
 * 
 * USAGE:
 * - Use to conditionally execute code based on environment
 * - Prefer explicit render mode declaration over this check
 * 
 * @returns "server" if running on server, "client" if running on client
 */
export function getCurrentRenderEnvironment(): RenderMode {
  return typeof window === "undefined" ? "server" : "client";
}

/**
 * Assert that code is running in expected environment
 * 
 * USAGE:
 * - Guard code that must only run on server or client
 * - Prevents hydration mismatches from environment-specific code
 * 
 * @param expected - Expected render environment
 * @throws Error if current environment doesn't match expected
 * 
 * @example
 * // Ensure code only runs on client
 * assertRenderEnvironment("client");
 * window.localStorage.setItem("key", "value");
 * 
 * @example
 * // Ensure code only runs on server
 * assertRenderEnvironment("server");
 * const secretKey = process.env.SECRET_KEY;
 */
export function assertRenderEnvironment(expected: RenderMode): void {
  const current = getCurrentRenderEnvironment();
  if (current !== expected) {
    throw new Error(
      `INVARIANT VIOLATION: Code expected to run in "${expected}" environment, ` +
      `but currently running in "${current}" environment. ` +
      `This may cause hydration mismatches or security issues.`
    );
  }
}
