import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IEpisodes } from "@/types/episodes";
import { useQuery } from "react-query";

type BackendRelease = {
  id: string;
  anime_id: string;
};

type BackendEpisode = {
  id: string;
  number: number;
  title?: string | null;
};

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

  const episodes =
    (res.data || []).map((episode) => ({
      title: episode.title || `Episode ${episode.number}`,
      episodeId: episode.id,
      number: episode.number,
      isFiller: false,
    })) || [];

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
