import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeDetails } from "@/types/anime-details";
import { useQuery } from "react-query";
import { PLACEHOLDER_POSTER } from "@/utils/constants";
import { mapReleaseArrayToSeasonArray } from "@/mappers/anime.mapper";
import { assertInternalApiResponse, assertInternalArrayResponse, assertString, assertOptional, assertNumber, assertArray } from "@/lib/contract-guards";
import { withRetry, INTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

const getAnimeDetails = async (animeId: string) => {
  const animeEndpoint = `/anime/${animeId}`;
  const releasesEndpoint = "/releases";
  
  const emptyDetails: IAnimeDetails = {
    anime: {
      info: {
        id: animeId,
        anilistId: 0,
        malId: 0,
        name: "",
        poster: PLACEHOLDER_POSTER,
        description: "",
        stats: {
          rating: "",
          quality: "",
          episodes: { sub: 0, dub: 0 },
          type: "Unknown",
          duration: "",
        },
        promotionalVideos: [],
        charactersVoiceActors: [],
      },
      moreInfo: {
        japanese: "",
        synonyms: "",
        aired: "N/A",
        premiered: "",
        duration: "",
        status: "Unknown",
        malscore: "",
        genres: [],
        studios: "",
        producers: [],
      },
    },
    seasons: [],
    mostPopularAnimes: [],
    relatedAnimes: [],
    recommendedAnimes: [],
  };

  return withRetry(
    async () => {
      try {
        const [animeRes, releasesRes] = await Promise.all([
          api.get(animeEndpoint),
          api.get(releasesEndpoint, { params: { limit: 100, offset: 0 } }),
        ]);

        // Internal API - Kitsu backend contract guaranteed
        assertInternalApiResponse(animeRes.data, animeEndpoint);
        const anime = animeRes.data;
        
        assertString(anime.id, "Anime.id");
        assertString(anime.title, "Anime.title");

        // Internal API - Kitsu backend contract guaranteed
        assertInternalArrayResponse(releasesRes.data, releasesEndpoint);
        assertArray(releasesRes.data, releasesEndpoint);
        
        // Filter releases for this anime
        const filteredReleases = (releasesRes.data as unknown[]).filter((release: unknown) => {
          if (typeof release !== 'object' || release === null) return false;
          return (release as Record<string, unknown>).anime_id === animeId;
        });

        const seasons = mapReleaseArrayToSeasonArray(filteredReleases);

        const description = assertOptional(anime.description, assertString, "Anime.description") ?? "";
        const titleOriginal = assertOptional(anime.title_original, assertString, "Anime.title_original") ?? anime.title;
        const status = assertOptional(anime.status, assertString, "Anime.status") ?? "Unknown";
        const year = assertOptional(anime.year, assertNumber, "Anime.year");

        return {
          ...emptyDetails,
          anime: {
            info: {
              ...emptyDetails.anime.info,
              id: anime.id,
              name: anime.title,
              description,
              stats: {
                rating: status,
                quality: "",
                episodes: { sub: 0, dub: 0 },
                type: status,
                duration: "",
              },
            },
            moreInfo: {
              ...emptyDetails.anime.moreInfo,
              japanese: titleOriginal,
              aired: year ? year.toString() : "N/A",
              status,
            },
          },
          seasons,
        };
      } catch (error) {
        // Map ContractError to ApiContractError
        throw normalizeToApiError(error, animeEndpoint);
      }
    },
    INTERNAL_API_POLICY,
    animeEndpoint
  );
};

export const useGetAnimeDetails = (animeId: string) => {
  return useQuery({
    queryFn: () => getAnimeDetails(animeId),
    queryKey: queryKeys.animeDetails(animeId),
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    retry: false,
    useErrorBoundary: (error) => {
      // Use error boundary for contract errors and all internal API errors
      return error instanceof ApiContractError || (error instanceof Error && !(error as Error & { source?: string }).source);
    },
  });
};
