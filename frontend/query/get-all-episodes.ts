import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IEpisodes } from "@/types/episodes";
import { useQuery } from "react-query";
import { BackendRelease, BackendEpisode } from "@/mappers/common";
import { mapBackendEpisodeToEpisode } from "@/mappers/episode.mapper";
import { assertInternalArrayResponse, assertString } from "@/lib/contract-guards";

const getAllEpisodes = async (animeId: string) => {
  const releasesRes = await api.get<BackendRelease[]>("/releases", {
    params: { limit: 100, offset: 0 },
  });
  
  // Internal API - Kitsu backend contract guaranteed
  assertInternalArrayResponse(releasesRes.data, "GET /releases");
  const release = (releasesRes.data as BackendRelease[]).find(
    (item) => item.anime_id === animeId,
  );

  if (!release) {
    return { totalEpisodes: 0, episodes: [] } as IEpisodes;
  }

  assertString(release.id, "Release.id");

  const res = await api.get<BackendEpisode[]>("/episodes", {
    params: { release_id: release.id },
  });

  // Internal API - Kitsu backend contract guaranteed
  assertInternalArrayResponse(res.data, "GET /episodes");
  const episodes = (res.data as BackendEpisode[]).map(mapBackendEpisodeToEpisode);

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
