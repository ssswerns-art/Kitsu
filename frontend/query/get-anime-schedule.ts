import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeSchedule } from "@/types/anime-schedule";
import { useQuery } from "react-query";
import { assertExternalApiShape, assertFieldExists } from "@/lib/contract-guards";

const getAnimeSchedule = async (date: string) => {
  const queryParams = date ? `?date=${date}` : "";

  const res = await api.get("/api/schedule" + queryParams, { timeout: 10000 });
  
  // External API - proxy/third-party, schema not guaranteed
  assertExternalApiShape(res.data, "GET /api/schedule");
  assertFieldExists(res.data, 'data', "GET /api/schedule");
  
  return res.data.data as IAnimeSchedule;
};

export const useGetAnimeSchedule = (
  date: string,
  options?: { enabled?: boolean },
) => {
  return useQuery({
    queryFn: () => getAnimeSchedule(date),
    queryKey: queryKeys.animeSchedule(date),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 5,
    enabled: options?.enabled ?? true,
  });
};
