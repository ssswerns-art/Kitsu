import { useMutation } from "react-query";
import { fetchUserAnimeList } from "@/external/anilist/anilist.adapter";

const getAnilistAnimes = async (username: string) => {
  // Mutation layer calls ONLY adapter functions
  // No knowledge of GraphQL, axios, retry logic, or external API contracts
  return fetchUserAnimeList(username);
};

export const useGetAnilistAnimes = () => {
  return useMutation({
    mutationFn: getAnilistAnimes,
    onError: (error) => {
      console.error("Error fetching Anilist animes:", error);
    },
  });
};
