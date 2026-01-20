import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { ISuggestionAnime } from "@/types/anime";
import { useQuery } from "react-query";
import { normalizeSearchQuery } from "./search-normalize";
import { BackendAnimeDTO } from "@/mappers/common";
import { mapSuggestionAnime } from "@/mappers/anime.mapper";

const searchAnime = async (q: string) => {
  if (q === "") {
    return;
  }
  const res = await api.get("/search/anime", {
    params: {
      q,
      limit: 5,
      offset: 0,
    },
  });

  return (res.data || []).map((anime: BackendAnimeDTO) => mapSuggestionAnime(anime));
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
