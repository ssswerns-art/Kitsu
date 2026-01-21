import { queryKeys } from "@/constants/query-keys";
import { IEpisodeServers } from "@/types/episodes";
import { useQuery } from "react-query";
import { ApiContractError } from "@/lib/api-errors";
import { fetchEpisodeServers } from "@/external/proxy/proxy.adapter";

const getEpisodeServers = async (episodeId: string): Promise<IEpisodeServers> => {
  // Query layer calls ONLY adapter functions
  // No knowledge of URLs, axios, retry logic, or external API contracts
  return fetchEpisodeServers(episodeId);
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
