import { queryKeys } from "@/constants/query-keys";
import { IEpisodeServers } from "@/types/episodes";
import { useQuery } from "react-query";
import { api } from "@/lib/api";
import { assertExternalApiShape, assertFieldExists } from "@/lib/contract-guards";
import { withRetryAndFallback, EXTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

const getEpisodeServers = async (episodeId: string) => {
  const endpoint = "/api/episode/servers";
  
  // Fallback for external API when retries exhausted
  const fallback: IEpisodeServers = {
    episodeId: "",
    episodeNo: "",
    sub: [],
    dub: [],
    raw: [],
  };

  if (!episodeId) return fallback;

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.get(endpoint, {
          params: {
            animeEpisodeId: decodeURIComponent(episodeId),
          },
          timeout: 10000,
        });
        
        // External API - proxy/third-party, schema not guaranteed
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as IEpisodeServers;
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

export const useGetEpisodeServers = (episodeId: string) => {
  return useQuery({
    queryFn: () => getEpisodeServers(episodeId),
    queryKey: queryKeys.episodeServers(episodeId),
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 3,
    enabled: Boolean(episodeId),
    retry: false,
    useErrorBoundary: (error) => {
      // Only use error boundary for contract errors
      return error instanceof ApiContractError;
    },
  });
};
