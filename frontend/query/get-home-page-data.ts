import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeData, Type } from "@/types/anime";
import { QueryFunction, UseQueryOptions, useQuery } from "react-query";
import { BackendAnimeDTO } from "@/mappers/common";
import { 
  mapAnimeList, 
  mapSpotlightAnime, 
  mapTopUpcomingAnime, 
  mapLatestCompletedAnime 
} from "@/mappers/anime.mapper";

const withTypeFallback = (type?: Type) => type ?? Type.Tv;

const getHomePageData: QueryFunction<
  IAnimeData,
  ReturnType<typeof queryKeys.homePage>
> = async () => {
  const emptyData: IAnimeData = {
    spotlightAnimes: [],
    trendingAnimes: [],
    latestEpisodeAnimes: [],
    topUpcomingAnimes: [],
    top10Animes: {
      today: [],
      week: [],
      month: [],
    },
    topAiringAnimes: [],
    mostPopularAnimes: [],
    mostFavoriteAnimes: [],
    latestCompletedAnimes: [],
    genres: [],
  };

  const res = await api.get<BackendAnimeDTO[]>("/anime", {
    params: { limit: 20, offset: 0 },
  });
  const animeList = mapAnimeList(res.data || []);
  const spotlightAnimes = (res.data || []).slice(0, 5).map((dto, idx) => 
    mapSpotlightAnime(dto, idx + 1)
  );
  const topUpcomingAnimes = (res.data || []).map(mapTopUpcomingAnime);
  const latestCompleted = (res.data || []).map(mapLatestCompletedAnime);

  const data: IAnimeData = {
    ...emptyData,
    spotlightAnimes,
    trendingAnimes: animeList,
    latestEpisodeAnimes: latestCompleted,
    topUpcomingAnimes,
    top10Animes: {
      today: latestCompleted.slice(0, 10),
      week: animeList.slice(0, 10),
      month: latestCompleted.slice(0, 10),
    },
    topAiringAnimes: latestCompleted,
    mostPopularAnimes: animeList,
    mostFavoriteAnimes: animeList,
    latestCompletedAnimes: latestCompleted,
  };

  return data;
};

export const useGetHomePageData = (
  options?: UseQueryOptions<
    IAnimeData,
    Error,
    IAnimeData,
    ReturnType<typeof queryKeys.homePage>
  >,
) => {
  return useQuery<IAnimeData, Error, IAnimeData, ReturnType<typeof queryKeys.homePage>>({
    queryFn: getHomePageData,
    queryKey: queryKeys.homePage(),
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 5, // 5 minutes
    cacheTime: 1000 * 60 * 10, // 10 minutes
    retry: false,
    ...options,
  });
};
