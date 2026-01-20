import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { useQuery } from "react-query";
import { assertExternalApiShape, assertFieldExists } from "@/lib/contract-guards";
import { withRetryAndFallback, EXTERNAL_API_POLICY } from "@/lib/api-retry";
import { ApiContractError, normalizeToApiError } from "@/lib/api-errors";

interface IAnimeBanner {
  Media: {
    id: number;
    bannerImage: string;
  };
}

const getAnimeBanner = async (anilistID: number) => {
  const endpoint = "https://graphql.anilist.co";
  
  // Fallback for external API when retries exhausted
  const fallback: IAnimeBanner = {
    Media: {
      id: anilistID,
      bannerImage: "",
    },
  };

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.post(
          endpoint,
          {
            query: `
            query ($id: Int) {
              Media(id: $id, type: ANIME) {
                id
                bannerImage
              }
            }
          `,
            variables: {
              id: anilistID,
            },
          },
          { timeout: 10000 },
        );
        
        // External API - GraphQL AniList, schema not guaranteed
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as IAnimeBanner;
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

export const useGetAnimeBanner = (anilistID: number) => {
  return useQuery({
    queryFn: () => getAnimeBanner(anilistID),
    queryKey: queryKeys.animeBanner(anilistID),
    enabled: !!anilistID,
    staleTime: 1000 * 60 * 60,
    refetchOnWindowFocus: false,
    retry: false,
    useErrorBoundary: (error) => {
      // Only use error boundary for contract errors
      return error instanceof ApiContractError;
    },
  });
};
