import { queryKeys } from "@/constants/query-keys";
import { IEpisodeSource } from "@/types/episodes";
import { useQuery } from "react-query";
import { api } from "@/lib/api";
import { assertExternalApiShape, assertFieldExists } from "@/lib/contract-guards";
import { withRetryAndFallback, EXTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

const getEpisodeData = async (
  episodeId: string,
  server: string | undefined,
  subOrDub: string,
) => {
  const endpoint = "/api/episode/sources";
  
  // Fallback for external API when retries exhausted
  const fallback: IEpisodeSource = {
    headers: { Referer: "" },
    tracks: [],
    intro: { start: 0, end: 0 },
    outro: { start: 0, end: 0 },
    sources: [],
    anilistID: 0,
    malID: 0,
  };

  if (!episodeId) return fallback;

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.get(endpoint, {
          params: {
            animeEpisodeId: decodeURIComponent(episodeId),
            server: server,
            category: subOrDub,
          },
          timeout: 10000,
        });
        
        // External API - proxy/third-party, schema not guaranteed
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as IEpisodeSource;
      } catch (error) {
        // Map ContractError to ApiContractError
        throw normalizeToApiError(error, endpoint);
      }
    },
    EXTERNAL_API_POLICY,
    endpoint,
    fallback
  );
};

export const useGetEpisodeData = (
  episodeId: string,
  server: string | undefined,
  subOrDub: string = "sub",
) => {
  return useQuery({
    queryFn: () => getEpisodeData(episodeId, server, subOrDub),
    queryKey: queryKeys.episodeData(episodeId, server, subOrDub),
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 3,
    enabled: Boolean(episodeId) && server !== "",
    retry: false,
    useErrorBoundary: (error) => {
      // Only use error boundary for contract errors
      return error instanceof ApiContractError;
    },
  });
};
