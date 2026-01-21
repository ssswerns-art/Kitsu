import { queryKeys } from "@/constants/query-keys";
import { IEpisodeSource } from "@/types/episodes";
import { useQuery } from "react-query";
import { ApiContractError } from "@/lib/api-errors";
import { fetchEpisodeSources } from "@/external/proxy/proxy.adapter";

const getEpisodeData = async (
  episodeId: string,
  server: string | undefined,
  subOrDub: string,
): Promise<IEpisodeSource> => {
  // Query layer calls ONLY adapter functions
  // No knowledge of URLs, axios, retry logic, or external API contracts
  return fetchEpisodeSources(episodeId, server, subOrDub);
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
