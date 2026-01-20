import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeDetails } from "@/types/anime-details";
import { useQuery } from "react-query";
import { PLACEHOLDER_POSTER } from "@/utils/constants";
import { BackendAnime, BackendRelease } from "@/mappers/common";
import { mapBackendReleaseToSeason } from "@/mappers/anime.mapper";
import { assertApiSuccessResponse, assertArrayResponse, assertString, assertOptional, assertNumber } from "@/lib/contract-guards";

const getAnimeDetails = async (animeId: string) => {
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

  const [animeRes, releasesRes] = await Promise.all([
    api.get<BackendAnime>(`/anime/${animeId}`),
    api.get<BackendRelease[]>("/releases", { params: { limit: 100, offset: 0 } }),
  ]);

  assertApiSuccessResponse(animeRes.data);
  const anime = animeRes.data as BackendAnime;
  
  assertString(anime.id, "Anime.id");
  assertString(anime.title, "Anime.title");

  assertArrayResponse(releasesRes.data);
  const releases = (releasesRes.data as BackendRelease[]).filter((release) => release.anime_id === animeId);

  const seasons = releases.map((release, idx) => 
    mapBackendReleaseToSeason(release, idx === 0)
  );

  const description: string = assertOptional(anime.description, (v) => assertString(v, "Anime.description"))
    ? anime.description as string
    : "";

  const titleOriginal: string = assertOptional(anime.title_original, (v) => assertString(v, "Anime.title_original"))
    ? anime.title_original as string
    : anime.title;

  const status: string = assertOptional(anime.status, (v) => assertString(v, "Anime.status"))
    ? anime.status as string
    : "Unknown";

  const year: number | null = assertOptional(anime.year, (v) => assertNumber(v, "Anime.year"))
    ? anime.year as number
    : null;

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
};

export const useGetAnimeDetails = (animeId: string) => {
  return useQuery({
    queryFn: () => getAnimeDetails(animeId),
    queryKey: queryKeys.animeDetails(animeId),
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    retry: false,
  });
};
