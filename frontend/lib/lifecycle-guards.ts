/**
 * Lifecycle Guards — Runtime Invariant Enforcement
 * ==================================================
 * 
 * This module provides runtime guards to enforce SSR/CSR lifecycle contracts.
 * 
 * ARCHITECTURAL INVARIANTS (enforced at runtime):
 * 
 * 1. NO CLIENT FETCH AFTER SSR
 *    - If data was fetched during SSR, CSR must NOT re-fetch
 *    - React Query cache or server snapshot must be used
 *    - Duplicate fetches are considered architectural errors
 * 
 * 2. SUSPENSE BOUNDARY PRESENCE
 *    - All data fetching MUST occur within Suspense boundary
 *    - No data fetching outside Suspense is allowed
 *    - Suspense controls loading states, not components
 * 
 * 3. NO EXTERNAL ADAPTERS IN UI
 *    - UI components MUST NOT import external adapters
 *    - External API calls MUST go through query layer
 *    - Adapter imports in UI violate architecture
 * 
 * 4. NO TRY/CATCH IN UI
 *    - UI components MUST NOT have try/catch blocks
 *    - Error boundaries handle all errors
 *    - Try/catch in UI violates error handling contract
 * 
 * ENFORCEMENT STRATEGY:
 * - Development: Guards throw errors immediately
 * - Production: Guards log warnings (avoid breaking user experience)
 * 
 * USAGE:
 * These guards are called automatically by the framework layer.
 * Manual calls should be rare and only for specific enforcement.
 */

import { getCurrentRenderEnvironment } from "./render-mode";

/**
 * Track SSR fetch operations to detect duplicate CSR fetches
 * 
 * IMPLEMENTATION:
 * - Server: Store fetched endpoints
 * - Client: Check against SSR fetches before allowing new fetches
 */
const ssrFetchedEndpoints = new Set<string>();

/**
 * Track whether we're in initial hydration phase
 */
let isHydrationComplete = false;

/**
 * Mark hydration as complete
 * Should be called by framework after initial hydration
 */
export function markHydrationComplete(): void {
  isHydrationComplete = true;
}

/**
 * Register that an endpoint was fetched during SSR
 * 
 * INVARIANT:
 * - Only called on server side
 * - Endpoint should not already be registered
 * 
 * @param endpoint - API endpoint that was fetched
 */
export function registerSSRFetch(endpoint: string): void {
  const env = getCurrentRenderEnvironment();
  if (env === "server") {
    ssrFetchedEndpoints.add(endpoint);
  }
}

/**
 * Assert that no client fetch occurs for data already fetched on SSR
 * 
 * INVARIANT:
 * - If endpoint was fetched on SSR, CSR must NOT re-fetch it
 * - Exception: Explicit refetch (user action, stale data)
 * 
 * ENFORCEMENT:
 * - Development: Throws error
 * - Production: Logs warning
 * 
 * @param endpoint - API endpoint being fetched on client
 * @param reason - Reason for fetch (e.g., "initial", "refetch", "user-action")
 * @throws Error in development if fetch violates SSR contract
 * 
 * @example
 * assertNoClientFetchAfterSSR("/anime", "initial");
 */
export function assertNoClientFetchAfterSSR(
  endpoint: string,
  reason: "initial" | "refetch" | "user-action" = "initial"
): void {
  const env = getCurrentRenderEnvironment();
  
  // Only check on client side
  if (env !== "client") {
    return;
  }
  
  // Allow refetches and user-initiated actions
  if (reason !== "initial") {
    return;
  }
  
  // During hydration, allow fetches (they may be from cache)
  if (!isHydrationComplete) {
    return;
  }
  
  // Check if endpoint was fetched on SSR
  if (ssrFetchedEndpoints.has(endpoint)) {
    const message =
      `INVARIANT VIOLATION: Client attempted to fetch "${endpoint}" after SSR. ` +
      `Data should be reused from SSR via React Query cache or server snapshot. ` +
      `Duplicate fetches violate single source of truth principle.`;
    
    if (process.env.NODE_ENV === "production") {
      // eslint-disable-next-line no-console
      console.warn(message);
    } else {
      throw new Error(message);
    }
  }
}

/**
 * Assert that Suspense boundary is present in component tree
 * 
 * INVARIANT:
 * - All data fetching MUST occur within Suspense boundary
 * - Components that fetch data must be wrapped in Suspense
 * 
 * IMPLEMENTATION NOTE:
 * This is a documentation guard. React will throw if Suspense is missing.
 * We include this for completeness of the contract.
 * 
 * @param componentName - Name of component that requires Suspense
 * 
 * @example
 * assertSuspenseBoundaryPresent("HomePageDataFetcher");
 */
export function assertSuspenseBoundaryPresent(componentName: string): void {
  // This is primarily a documentation guard
  // React's Suspense will throw its own error if boundary is missing
  // We log in development to make the contract explicit
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.debug(
      `[Lifecycle Guard] ${componentName} requires Suspense boundary. ` +
      `Ensure component is wrapped in <Suspense> or has Suspense ancestor.`
    );
  }
}

/**
 * Assert that external adapters are not imported in UI components
 * 
 * INVARIANT:
 * - UI components MUST NOT import external adapters directly
 * - External API calls MUST go through query layer
 * - Adapters are infrastructure, not UI concerns
 * 
 * USAGE:
 * Call this from adapter modules to detect UI imports
 * 
 * @param adapterName - Name of the adapter being imported
 * @param importLocation - File/component that is importing the adapter
 * @throws Error if UI component imports adapter
 * 
 * @example
 * // In adapter file
 * assertNoExternalAdapterInUI("AniListAdapter", "components/hero-section");
 */
export function assertNoExternalAdapterInUI(
  adapterName: string,
  importLocation: string
): void {
  // Check if import location is in components, app, or UI directories
  const uiPatterns = [
    /\/components\//,
    /\/app\//,
    /\/ui\//,
    /\/pages\//,
  ];
  
  const isUIImport = uiPatterns.some(pattern => pattern.test(importLocation));
  
  if (isUIImport) {
    const message =
      `INVARIANT VIOLATION: UI component "${importLocation}" imported external adapter "${adapterName}". ` +
      `UI components MUST NOT import adapters directly. ` +
      `Use query layer (query/*.ts) to access external APIs.`;
    
    if (process.env.NODE_ENV === "production") {
      // eslint-disable-next-line no-console
      console.warn(message);
    } else {
      throw new Error(message);
    }
  }
}

/**
 * Assert that no try/catch exists in UI components
 * 
 * INVARIANT:
 * - UI components MUST NOT use try/catch for error handling
 * - Error boundaries handle all errors
 * - Try/catch in UI violates declarative error handling
 * 
 * USAGE:
 * This is primarily a linting/code review concern
 * Runtime detection is limited
 * 
 * @param componentName - Name of component being checked
 * 
 * @example
 * assertNoTryCatchInUI("HeroSection");
 */
export function assertNoTryCatchInUI(componentName: string): void {
  // This is primarily a linting concern
  // Runtime detection is difficult without code analysis
  // We provide this for documentation and optional manual checks
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.debug(
      `[Lifecycle Guard] ${componentName} must not use try/catch. ` +
      `Use Error Boundaries for error handling instead.`
    );
  }
}

/**
 * Development-only comprehensive lifecycle check
 * 
 * Performs all lifecycle checks for a component
 * Should be called at component mount in development
 * 
 * @param componentName - Name of component being checked
 * @param config - Configuration for lifecycle checks
 */
export function assertLifecycleContract(
  componentName: string,
  config: {
    requiresSuspense?: boolean;
    fetchesData?: boolean;
    endpoint?: string;
  } = {}
): void {
  if (process.env.NODE_ENV === "production") {
    return;
  }
  
  if (config.requiresSuspense) {
    assertSuspenseBoundaryPresent(componentName);
  }
  
  if (config.fetchesData && config.endpoint) {
    assertNoClientFetchAfterSSR(config.endpoint, "initial");
  }
  
  assertNoTryCatchInUI(componentName);
}
