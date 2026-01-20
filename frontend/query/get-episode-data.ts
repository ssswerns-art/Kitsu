import { queryKeys } from "@/constants/query-keys";
import { IEpisodeSource } from "@/types/episodes";
import { useQuery } from "react-query";
import { api } from "@/lib/api";

const getEpisodeData = async (
  episodeId: string,
  server: string | undefined,
  subOrDub: string,
) => {
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

  const res = await api.get("/api/episode/sources", {
    params: {
      animeEpisodeId: decodeURIComponent(episodeId),
      server: server,
      category: subOrDub,
    },
    timeout: 10000,
  });
  return res.data.data as IEpisodeSource;
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
  });
};
