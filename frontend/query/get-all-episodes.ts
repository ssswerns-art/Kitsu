import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IEpisodes } from "@/types/episodes";
import { useQuery } from "react-query";
import { BackendRelease, BackendEpisode } from "@/mappers/common";
import { mapBackendEpisodeToEpisode } from "@/mappers/episode.mapper";

const getAllEpisodes = async (animeId: string) => {
  const releasesRes = await api.get<BackendRelease[]>("/releases", {
    params: { limit: 100, offset: 0 },
  });
  const release = (releasesRes.data || []).find(
    (item) => item.anime_id === animeId,
  );

  if (!release) {
    return { totalEpisodes: 0, episodes: [] } as IEpisodes;
  }

  const res = await api.get<BackendEpisode[]>("/episodes", {
    params: { release_id: release.id },
  });

  const episodes = (res.data || []).map(mapBackendEpisodeToEpisode);

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
