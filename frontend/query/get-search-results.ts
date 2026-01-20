import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeSearch, SearchAnimeParams } from "@/types/anime";
import { useQuery } from "react-query";
import { PLACEHOLDER_POSTER } from "@/utils/constants";
import { normalizeSearchParams } from "./search-normalize";

type BackendAnime = {
  id: string;
  title: string;
  title_original?: string | null;
  status?: string | null;
  year?: number | null;
};

const searchAnime = async (params: SearchAnimeParams) => {
  const limit = 20;
  const currentPage = params.page || 1;
  const offset = (currentPage - 1) * limit;

  const res = await api.get<BackendAnime[]>("/search/anime", {
    params: { q: params.q, limit, offset },
  });

  const animes = (res.data || []).map((anime) => ({
    id: anime.id,
    name: anime.title,
    jname: anime.title_original || anime.title,
    poster: PLACEHOLDER_POSTER,
    episodes: { sub: null, dub: null },
    type: anime.status || undefined,
    rank: undefined,
  }));

  const hasNextPage = animes.length === limit;
  const estimatedTotal =
    animes.length === 0 || animes.length < limit
      ? currentPage
      : currentPage + 1;

  return {
    animes,
    totalPages: estimatedTotal,
    hasNextPage,
    currentPage,
  };
};

export const useGetSearchAnimeResults = (params: SearchAnimeParams) => {
  const normalizedParams: SearchAnimeParams = normalizeSearchParams(params);

  return useQuery({
    queryFn: () => searchAnime(normalizedParams),
    queryKey: queryKeys.searchAnime(normalizedParams.q, normalizedParams.page),
    enabled: normalizedParams.q.length >= 2,
    staleTime: 1000 * 60 * 2,
    refetchOnWindowFocus: false,
    retry: false,
  });
};
