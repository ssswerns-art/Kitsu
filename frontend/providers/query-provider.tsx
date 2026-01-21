"use client";

import React, { ReactNode, useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "react-query";
import { shouldUseErrorBoundary } from "@/lib/error-boundary-policy";
import { markHydrationComplete } from "@/lib/lifecycle-guards";

type Props = {
  children: ReactNode;
};

const DEFAULT_STALE_TIME = 1000 * 60 * 5;
const DEFAULT_CACHE_TIME = 1000 * 60 * 10;

/**
 * Query Provider with SSR/CSR Lifecycle Guarantees
 * 
 * ARCHITECTURAL INVARIANTS:
 * 
 * 1. SINGLE SOURCE OF TRUTH
 *    - Cache ensures data fetched on SSR is reused on CSR
 *    - No duplicate requests between SSR and CSR
 *    - staleTime and cacheTime prevent unnecessary refetches
 * 
 * 2. ERROR BOUNDARY POLICY
 *    - Uses error-boundary-policy to determine error handling
 *    - Contract errors → crash (useErrorBoundary: true)
 *    - Internal errors → crash (useErrorBoundary: true)
 *    - External errors → degrade (useErrorBoundary: false)
 * 
 * 3. NO RETRY IN QUERY CLIENT
 *    - Retry is handled by api-retry layer
 *    - Query client retry is disabled (retry: false)
 *    - Prevents double retry (query + api layer)
 * 
 * 4. HYDRATION TRACKING
 *    - Marks hydration complete for lifecycle guards
 *    - Enables duplicate fetch detection
 */
const QueryProvider = (props: Props) => {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Cache configuration for SSR/CSR single source of truth
            staleTime: DEFAULT_STALE_TIME,
            cacheTime: DEFAULT_CACHE_TIME,
            
            // Disable automatic refetch on window focus
            // Prevents duplicate fetches when user returns to tab
            refetchOnWindowFocus: false,
            
            // Disable query-level retry (handled by api-retry layer)
            retry: false,
            
            // Use error boundary policy for error handling
            // Determines if error should crash or degrade gracefully
            useErrorBoundary: (error) => shouldUseErrorBoundary(error),
            
            // Disable automatic refetch on mount after SSR
            // Data from SSR should be reused, not refetched
            refetchOnMount: false,
          },
        },
      }),
  );

  // Mark hydration complete for lifecycle guards
  useEffect(() => {
    markHydrationComplete();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {props.children}
    </QueryClientProvider>
  );
};

export default QueryProvider;
