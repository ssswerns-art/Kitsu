import { queryKeys } from "@/constants/query-keys";
import { api } from "@/lib/api";
import { useQuery } from "react-query";
import { assertExternalApiShape, assertFieldExists } from "@/lib/contract-guards";

interface IAnimeBanner {
  Media: {
    id: number;
    bannerImage: string;
  };
}

const getAnimeBanner = async (anilistID: number) => {
  const res = await api.post(
    "https://graphql.anilist.co",
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
  assertExternalApiShape(res.data, "POST graphql.anilist.co");
  assertFieldExists(res.data, 'data', "POST graphql.anilist.co");
  
  return res.data.data as IAnimeBanner;
};

export const useGetAnimeBanner = (anilistID: number) => {
  return useQuery({
    queryFn: () => getAnimeBanner(anilistID),
    queryKey: queryKeys.animeBanner(anilistID),
    enabled: !!anilistID,
    staleTime: 1000 * 60 * 60,
    refetchOnWindowFocus: false,
    retry: false,
  });
};
