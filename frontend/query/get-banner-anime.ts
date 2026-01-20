import { queryKeys } from "@/constants/query-keys";
import { useQuery } from "react-query";
import { ApiContractError } from "@/lib/api-errors";
import { fetchAnimeBanner } from "@/external/anilist/anilist.adapter";

interface IAnimeBanner {
  Media: {
    id: number;
    bannerImage: string;
  };
}

const getAnimeBanner = async (anilistID: number): Promise<IAnimeBanner> => {
  // Query layer calls ONLY adapter functions
  // No knowledge of GraphQL, axios, retry logic, or external API contracts
  return fetchAnimeBanner(anilistID);
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
