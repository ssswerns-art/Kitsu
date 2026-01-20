import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IEpisodes } from "@/types/episodes";
import { useQuery } from "react-query";
import { mapEpisodeArrayToEpisodeArray } from "@/mappers/episode.mapper";
import { assertInternalArrayResponse, assertString, assertObject } from "@/lib/contract-guards";

const getAllEpisodes = async (animeId: string) => {
  const releasesRes = await api.get("/releases", {
    params: { limit: 100, offset: 0 },
  });
  
  // Internal API - Kitsu backend contract guaranteed
  assertInternalArrayResponse(releasesRes.data, "GET /releases");
  
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

  const res = await api.get("/episodes", {
    params: { release_id: release.id },
  });

  // Internal API - Kitsu backend contract guaranteed
  assertInternalArrayResponse(res.data, "GET /episodes");
  const episodes = mapEpisodeArrayToEpisodeArray(res.data);

  return { totalEpisodes: episodes.length, episodes } as IEpisodes;
};

export const useGetAllEpisodes = (animeId: string) => {
  return useQuery({
    queryFn: () => getAllEpisodes(animeId),
    queryKey: queryKeys.allEpisodes(animeId),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 5,
  });
};
