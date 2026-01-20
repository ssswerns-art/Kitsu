import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { IAnimeSchedule } from "@/types/anime-schedule";
import { useQuery } from "react-query";
import { assertExternalApiShape, assertFieldExists } from "@/lib/contract-guards";
import { withRetryAndFallback, EXTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

const getAnimeSchedule = async (date: string) => {
  const endpoint = "/api/schedule";
  const queryParams = date ? `?date=${date}` : "";
  
  // Fallback for external API when retries exhausted
  const fallback: IAnimeSchedule = {
    scheduledAnimes: [],
  };

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.get(endpoint + queryParams, { timeout: 10000 });
        
        // External API - proxy/third-party, schema not guaranteed
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as IAnimeSchedule;
      } catch (error) {
        // Map ContractError to ApiContractError
        throw normalizeToApiError(error, endpoint);
      }
    },
    EXTERNAL_API_POLICY,
    endpoint,
    fallback
  );
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
