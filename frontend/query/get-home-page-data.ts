import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeData, SpotlightAnime, TopUpcomingAnime } from "@/types/anime";
import { QueryFunction, UseQueryOptions, useQuery } from "react-query";
import { 
  mapAnimeArrayToIAnimeArray,
  mapAnimeArrayToSpotlightAnimeArray,
  mapAnimeArrayToTopUpcomingAnimeArray
} from "@/mappers/anime.mapper";
import { assertInternalArrayResponse } from "@/lib/contract-guards";
import { withRetry, INTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

const getHomePageData: QueryFunction<
  IAnimeData,
  ReturnType<typeof queryKeys.homePage>
> = async () => {
  const endpoint = "/anime";
  
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

  return withRetry(
    async () => {
      try {
        const res = await api.get(endpoint, {
          params: { limit: 20, offset: 0 },
        });
        
        // Internal API - Kitsu backend contract guaranteed
        assertInternalArrayResponse(res.data, endpoint);
        
        const mapped = mapAnimeArrayToIAnimeArray(res.data);
        
        const spotlightAnimes: SpotlightAnime[] = mapAnimeArrayToSpotlightAnimeArray(res.data.slice(0, 5));
        
        const topUpcomingAnimes: TopUpcomingAnime[] = mapAnimeArrayToTopUpcomingAnimeArray(res.data);

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
      } catch (error) {
        // Map ContractError to ApiContractError
        throw normalizeToApiError(error, endpoint);
      }
    },
    INTERNAL_API_POLICY,
    endpoint
  );
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
    useErrorBoundary: (error) => {
      // Use error boundary for contract errors and all internal API errors
      return error instanceof ApiContractError || (error instanceof Error && !(error as Error & { source?: string }).source);
    },
    ...options,
  });
};
