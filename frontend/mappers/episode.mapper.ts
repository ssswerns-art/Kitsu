import { Episode } from "@/types/episodes";
import { BackendEpisode } from "./common";
import { assertString, assertNumber, assertOptional } from "@/lib/contract-guards";

/**
 * Maps BackendEpisode to Episode
 * PURE function - no fallbacks, no optional chaining
 */
export function mapBackendEpisodeToEpisode(dto: BackendEpisode): Episode {
  assertString(dto.id, "Episode.id");
  assertNumber(dto.number, "Episode.number");

  const title: string = assertOptional(dto.title, (v) => assertString(v, "Episode.title"))
    ? dto.title as string
    : `Episode ${dto.number}`;

  return {
    title,
    episodeId: dto.id,
    number: dto.number,
    isFiller: false,
  };
}
