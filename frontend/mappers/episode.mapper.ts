import { Episode } from "@/types/episodes";
import { assertString, assertNumber, assertOptional, assertArray } from "@/lib/contract-guards";

/**
 * Backend DTO Types (INTERNAL - NOT EXPORTED)
 * These represent the actual API response structure from backend (snake_case)
 * 
 * ⚠️ CRITICAL: These types are private implementation details of this mapper.
 * They MUST NOT be exported or used outside this file.
 * Query layer works only with Domain Models (Episode, etc.)
 */

type BackendEpisode = {
  id: string;
  number: number;
  title?: string | null;
};

/**
 * Type guards - internal helpers for safe casting from unknown
 */

function isBackendEpisode(data: unknown): data is BackendEpisode {
  return typeof data === 'object' && data !== null && 'id' in data && 'number' in data;
}

/**
 * Maps BackendEpisode to Episode
 * PURE function - no fallbacks, no optional chaining
 */
export function mapBackendEpisodeToEpisode(dto: BackendEpisode): Episode {
  assertString(dto.id, "Episode.id");
  assertNumber(dto.number, "Episode.number");

  const title = assertOptional(dto.title, assertString, "Episode.title") ?? `Episode ${dto.number}`;

  return {
    title,
    episodeId: dto.id,
    number: dto.number,
    isFiller: false,
  };
}

/**
 * Maps array of unknown data to Episode array
 * This is the ONLY function that query layer should use for mapping episode arrays
 */
export function mapEpisodeArrayToEpisodeArray(data: unknown): Episode[] {
  assertArray(data, "EpisodeArray");
  return data.map((item) => {
    if (!isBackendEpisode(item)) {
      throw new Error("Invalid episode data in array");
    }
    return mapBackendEpisodeToEpisode(item);
  });
}
