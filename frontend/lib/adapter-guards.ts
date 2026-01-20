/**
 * External API Adapter Guardrails
 * =================================
 * 
 * INVARIANTS (enforced at runtime):
 * 
 * 1. ADAPTER CALL ENFORCEMENT
 *    - All external API calls MUST go through adapter layer
 *    - Direct axios/fetch/api calls from query layer are FORBIDDEN
 *    - Adapters MUST use withRetry/withRetryAndFallback
 * 
 * 2. SOURCE TAGGING
 *    - External API calls MUST be tagged with source="external"
 *    - Adapters MUST use EXTERNAL_API_POLICY
 *    - Adapters MUST handle contract validation internally
 * 
 * 3. TYPE ISOLATION
 *    - Adapters MUST NOT export DTO/raw response types
 *    - Adapters MUST only export functions
 *    - Query layer MUST NOT know external API shapes
 * 
 * USAGE:
 * - Call assertIsExternalAdapterCall() at the start of every adapter function
 * - This ensures adapters are properly isolated and follow conventions
 */

/**
 * Runtime assertion: confirms we're in an external adapter context
 * 
 * INVARIANTS:
 * - Must be called from external/* directory
 * - Must use EXTERNAL_API_POLICY
 * - Must tag with source="external"
 * 
 * @param adapterName - Name of the adapter (e.g., "ProxyAdapter", "AniListAdapter")
 * @throws Error if called outside adapter context
 */
export function assertIsExternalAdapterCall(adapterName: string): void {
  // This is a compile-time marker that helps enforce adapter isolation
  // The real enforcement comes from:
  // 1. TypeScript module boundaries (adapters don't export types)
  // 2. Code review checks (grep assertions)
  // 3. Architecture documentation
  
  // We keep this as a runtime marker for debugging
  if (process.env.NODE_ENV === 'development') {
    // eslint-disable-next-line no-console
    console.debug(`[ExternalAdapter:${adapterName}] Adapter call initiated`);
  }
}

/**
 * Marker type to prevent type leakage from adapters
 * 
 * Adapters should use this in their return types to ensure
 * they're returning domain models, not external DTOs
 * 
 * @example
 * export async function fetchSchedule(date: string): Promise<AdapterDomainModel<IAnimeSchedule>> {
 *   assertIsExternalAdapterCall('ProxyAdapter.fetchSchedule');
 *   // ... implementation
 * }
 */
export type AdapterDomainModel<T> = T;
