import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeData, SpotlightAnime, TopUpcomingAnime } from "@/types/anime";
import { QueryFunction, UseQueryOptions, useQuery } from "react-query";
import { BackendAnime } from "@/mappers/common";
import { 
  mapBackendAnimeToIAnime,
  mapBackendAnimeToSpotlightAnime,
  mapBackendAnimeToTopUpcomingAnime
} from "@/mappers/anime.mapper";
import { assertInternalArrayResponse } from "@/lib/contract-guards";

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

  const res = await api.get<BackendAnime[]>("/anime", {
    params: { limit: 20, offset: 0 },
  });
  
  // Internal API - Kitsu backend contract guaranteed
  assertInternalArrayResponse(res.data, "GET /anime");
  
  const mapped = res.data.map(mapBackendAnimeToIAnime);
  
  const spotlightAnimes: SpotlightAnime[] = res.data
    .slice(0, 5)
    .map((anime, idx) => mapBackendAnimeToSpotlightAnime(anime, idx + 1));
  
  const topUpcomingAnimes: TopUpcomingAnime[] = res.data
    .map(mapBackendAnimeToTopUpcomingAnime);

  const data: IAnimeData = {
    ...emptyData,
    spotlightAnimes,
    trendingAnimes: mapped,
    latestEpisodeAnimes: mapped,
    topUpcomingAnimes,
    top10Animes: {
      today: mapped.slice(0, 10),
      week: mapped.slice(0, 10),
      month: mapped.slice(0, 10),
    },
    topAiringAnimes: mapped,
    mostPopularAnimes: mapped,
    mostFavoriteAnimes: mapped,
    latestCompletedAnimes: mapped,
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
