import { Episode } from "@/types/episodes";
import { BackendEpisode } from "./common";

/**
 * Maps BackendEpisode to Episode
 * PURE function - no fallbacks, no optional chaining
 */
export function mapBackendEpisodeToEpisode(dto: BackendEpisode): Episode {
  if (!dto.id) throw new Error("Episode.id is required");
  if (dto.number === undefined || dto.number === null) {
    throw new Error("Episode.number is required");
  }

  return {
    title: dto.title || `Episode ${dto.number}`,
    episodeId: dto.id,
    number: dto.number,
    isFiller: false,
  };
}
