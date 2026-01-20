import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeSearch, SearchAnimeParams } from "@/types/anime";
import { useQuery } from "react-query";
import { normalizeSearchParams } from "./search-normalize";
import { mapAnimeArrayToIAnimeArray } from "@/mappers/anime.mapper";
import { assertInternalArrayResponse } from "@/lib/contract-guards";
import { withRetry, INTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

const searchAnime = async (params: SearchAnimeParams) => {
  const endpoint = "/search/anime";
  const limit = 20;
  const currentPage = params.page || 1;
  const offset = (currentPage - 1) * limit;

  return withRetry(
    async () => {
      try {
        const res = await api.get(endpoint, {
          params: { q: params.q, limit, offset },
        });

        // Internal API - Kitsu backend contract guaranteed
        assertInternalArrayResponse(res.data, endpoint);
        const animes = mapAnimeArrayToIAnimeArray(res.data);

        const hasNextPage = animes.length === limit;
        const estimatedTotal =
          animes.length === 0 || animes.length < limit
            ? currentPage
            : currentPage + 1;

        return {
          animes,
          totalPages: estimatedTotal,
          hasNextPage,
          currentPage,
        };
      } catch (error) {
        // Map ContractError to ApiContractError
        throw normalizeToApiError(error, endpoint);
      }
    },
    INTERNAL_API_POLICY,
    endpoint
  );
};

export const useGetSearchAnimeResults = (params: SearchAnimeParams) => {
  const normalizedParams: SearchAnimeParams = normalizeSearchParams(params);

  return useQuery({
    queryFn: () => searchAnime(normalizedParams),
    queryKey: queryKeys.searchAnime(normalizedParams.q, normalizedParams.page),
    enabled: normalizedParams.q.length >= 2,
    staleTime: 1000 * 60 * 2,
    refetchOnWindowFocus: false,
    retry: false,
    useErrorBoundary: (error) => {
      // Use error boundary for contract errors and all internal API errors
      return error instanceof ApiContractError || (error instanceof Error && !(error as Error & { source?: string }).source);
    },
  });
};
