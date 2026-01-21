import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { ISuggestionAnime } from "@/types/anime";
import { useQuery } from "react-query";
import { normalizeSearchQuery } from "./search-normalize";
import { mapAnimeArrayToSuggestionAnimeArray } from "@/mappers/anime.mapper";
import { assertInternalArrayResponse } from "@/lib/contract-guards";
import { withRetry, INTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

const searchAnime = async (q: string) => {
  if (q === "") {
    return;
  }
  
  const endpoint = "/search/anime";
  
  return withRetry(
    async () => {
      try {
        const res = await api.get(endpoint, {
          params: {
            q,
            limit: 5,
            offset: 0,
          },
        });

        // Internal API - Kitsu backend contract guaranteed
        assertInternalArrayResponse(res.data, endpoint);
        return mapAnimeArrayToSuggestionAnimeArray(res.data);
      } catch (error) {
        // Map ContractError to ApiContractError
        throw normalizeToApiError(error, endpoint);
      }
    },
    INTERNAL_API_POLICY,
    endpoint
  );
};

export const useSearchAnime = (query: string) => {
  const normalizedQuery = normalizeSearchQuery(query);
  return useQuery({
    queryFn: () => searchAnime(normalizedQuery),
    queryKey: queryKeys.searchAnimeSuggestions(normalizedQuery),
    enabled: normalizedQuery.length >= 2,
    staleTime: 1000 * 60 * 2,
    refetchOnWindowFocus: false,
    retry: false,
    useErrorBoundary: (error) => {
      // Use error boundary for contract errors and all internal API errors
      return error instanceof ApiContractError || (error instanceof Error && !(error as Error & { source?: string }).source);
    },
  });
};
