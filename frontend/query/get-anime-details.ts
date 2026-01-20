import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeDetails } from "@/types/anime-details";
import { useQuery } from "react-query";
import { PLACEHOLDER_POSTER } from "@/utils/constants";

type BackendAnime = {
  id: string;
  title: string;
  title_original?: string | null;
  description?: string | null;
  year?: number | null;
  status?: string | null;
};

type BackendRelease = {
  id: string;
  anime_id: string;
  title: string;
  year?: number | null;
  status?: string | null;
};

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

  const anime = animeRes.data;
  const releases =
    (releasesRes.data || []).filter((release) => release.anime_id === animeId) ||
    [];

  const seasons = releases.map((release, idx) => ({
    id: release.id,
    name: release.title,
    title: release.title,
    poster: PLACEHOLDER_POSTER,
    isCurrent: idx === 0,
  }));

  return {
    ...emptyDetails,
    anime: {
      info: {
        ...emptyDetails.anime.info,
        id: anime.id,
        name: anime.title,
        description: anime.description || "",
        stats: {
          rating: anime.status || "",
          quality: "",
          episodes: { sub: 0, dub: 0 },
          type: anime.status || "Unknown",
          duration: "",
        },
      },
      moreInfo: {
        ...emptyDetails.anime.moreInfo,
        japanese: anime.title_original || anime.title,
        aired: anime.year ? anime.year.toString() : "N/A",
        status: anime.status || "Unknown",
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
