import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeSearch, SearchAnimeParams } from "@/types/anime";
import { useQuery } from "react-query";
import { normalizeSearchParams } from "./search-normalize";
import { BackendAnimeDTO } from "@/mappers/common";
import { mapAnimeList } from "@/mappers/anime.mapper";

const searchAnime = async (params: SearchAnimeParams) => {
  const limit = 20;
  const currentPage = params.page || 1;
  const offset = (currentPage - 1) * limit;

  const res = await api.get<BackendAnimeDTO[]>("/search/anime", {
    params: { q: params.q, limit, offset },
  });

  const animes = mapAnimeList(res.data || []);

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
