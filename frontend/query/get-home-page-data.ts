import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeData, SpotlightAnime, TopUpcomingAnime, Type } from "@/types/anime";
import { QueryFunction, UseQueryOptions, useQuery } from "react-query";
import { PLACEHOLDER_POSTER } from "@/utils/constants";

type BackendAnime = {
  id: string;
  title: string;
  title_original?: string | null;
  status?: string | null;
  year?: number | null;
};

const mapStatusToType = (status?: string | null): Type | undefined => {
  const normalizedStatus = status?.toUpperCase();

  switch (normalizedStatus) {
    case "TV":
      return Type.Tv;
    case "ONA":
      return Type.Ona;
    case "MOVIE":
      return Type.Movie;
    default:
      return undefined;
  }
};

const withTypeFallback = (type?: Type) => type ?? Type.Tv;

const mapAnimeList = (animes: BackendAnime[]) =>
  animes.map((anime) => ({
    id: anime.id,
    name: anime.title,
    jname: anime.title_original || anime.title,
    poster: PLACEHOLDER_POSTER,
    episodes: { sub: null, dub: null },
    type: withTypeFallback(mapStatusToType(anime.status)),
    rank: undefined,
    duration: "",
    rating: null,
  }));

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
  const mapped = mapAnimeList(res.data || []);
  const spotlightAnimes: SpotlightAnime[] = mapped.slice(0, 5).map((anime, idx) => ({
    rank: idx + 1,
    id: anime.id,
    name: anime.name,
    description: "",
    poster: anime.poster,
    jname: anime.jname,
    episodes: anime.episodes,
    type: withTypeFallback(anime.type),
    otherInfo: [],
  }));
  const topUpcomingAnimes: TopUpcomingAnime[] = mapped.map((anime) => ({
    id: anime.id,
    name: anime.name,
    jname: anime.jname,
    poster: anime.poster,
    duration: anime.duration || "",
    type: withTypeFallback(anime.type),
    rating: anime.rating,
    episodes: anime.episodes,
  }));

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
