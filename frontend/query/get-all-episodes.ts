import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IEpisodes } from "@/types/episodes";
import { useQuery } from "react-query";
import { mapEpisodeArrayToEpisodeArray } from "@/mappers/episode.mapper";
import { assertInternalArrayResponse, assertString, assertObject } from "@/lib/contract-guards";
import { withRetry, INTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

const getAllEpisodes = async (animeId: string) => {
  const releasesEndpoint = "/releases";
  const episodesEndpoint = "/episodes";
  
  return withRetry(
    async () => {
      try {
        const releasesRes = await api.get(releasesEndpoint, {
          params: { limit: 100, offset: 0 },
        });
        
        // Internal API - Kitsu backend contract guaranteed
        assertInternalArrayResponse(releasesRes.data, releasesEndpoint);
        
        // Find release for this anime - filter works on validated array
        const release = (releasesRes.data as unknown[]).find(
          (item: unknown) => {
            if (typeof item !== 'object' || item === null) return false;
            return (item as Record<string, unknown>).anime_id === animeId;
          }
        );

        if (!release) {
          return { totalEpisodes: 0, episodes: [] } as IEpisodes;
        }

        // Validate release is an object before accessing properties
        assertObject(release, "Release");
        assertString(release.id, "Release.id");

        const res = await api.get(episodesEndpoint, {
          params: { release_id: release.id },
        });

        // Internal API - Kitsu backend contract guaranteed
        assertInternalArrayResponse(res.data, episodesEndpoint);
        const episodes = mapEpisodeArrayToEpisodeArray(res.data);

        return { totalEpisodes: episodes.length, episodes } as IEpisodes;
      } catch (error) {
        // Map ContractError to ApiContractError
        throw normalizeToApiError(error, releasesEndpoint);
      }
    },
    INTERNAL_API_POLICY,
    releasesEndpoint
  );
};

export const useGetAllEpisodes = (animeId: string) => {
  return useQuery({
    queryFn: () => getAllEpisodes(animeId),
    queryKey: queryKeys.allEpisodes(animeId),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 5,
    useErrorBoundary: (error) => {
      // Use error boundary for contract errors and all internal API errors
      return error instanceof ApiContractError || (error instanceof Error && !(error as Error & { source?: string }).source);
    },
  });
};
