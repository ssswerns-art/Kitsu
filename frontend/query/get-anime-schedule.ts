import { queryKeys } from "@/constants/query-keys";
import { IAnimeSchedule } from "@/types/anime-schedule";
import { useQuery } from "react-query";
import { ApiContractError } from "@/lib/api-errors";
import { fetchAnimeSchedule } from "@/external/proxy/proxy.adapter";

const getAnimeSchedule = async (date: string): Promise<IAnimeSchedule> => {
  // Query layer calls ONLY adapter functions
  // No knowledge of URLs, axios, retry logic, or external API contracts
  return fetchAnimeSchedule(date);
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
    useErrorBoundary: (error) => {
      // Only use error boundary for contract errors
      return error instanceof ApiContractError;
    },
  });
};
