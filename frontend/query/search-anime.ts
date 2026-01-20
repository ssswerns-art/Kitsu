import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { ISuggestionAnime } from "@/types/anime";
import { useQuery } from "react-query";
import { normalizeSearchQuery } from "./search-normalize";
import { BackendAnime } from "@/mappers/common";
import { mapBackendAnimeToSuggestionAnime } from "@/mappers/anime.mapper";
import { assertInternalArrayResponse } from "@/lib/contract-guards";

const searchAnime = async (q: string) => {
  if (q === "") {
    return;
  }
  const res = await api.get<BackendAnime[]>("/search/anime", {
    params: {
      q,
      limit: 5,
      offset: 0,
    },
  });

  // Internal API - Kitsu backend contract guaranteed
  assertInternalArrayResponse(res.data, "GET /search/anime");
  return (res.data as BackendAnime[]).map(mapBackendAnimeToSuggestionAnime);
};

export const useSearchAnime = (query: string) => {
  const normalizedQuery = normalizeSearchQuery(query);
  return useQuery({
    queryFn: () => searchAnime(normalizedQuery),
    queryKey: queryKeys.searchAnimeSuggestions(normalizedQuery),
    enabled: normalizedQuery.length >= 2,
    staleTime: 1000 * 60 * 2,
    refetchOnWindowFocus: false,
    retry: false,
  });
};
