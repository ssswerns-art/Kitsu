/**
 * Common Backend DTO Types
 * These represent the actual API response structure from backend (snake_case)
 * 
 * IMPORTANT: These types are INTERNAL to the mapper layer and must NEVER be 
 * imported or used outside of frontend/mappers/* directory.
 * They are exported ONLY for use by other mapper files (anime.mapper.ts, episode.mapper.ts).
 */

type BackendAnime = {
  id: string;
  title: string;
  title_original?: string | null;
  description?: string | null;
  year?: number | null;
  status?: string | null;
};

type BackendRelease = {
  id: string;
  anime_id: string;
  title: string;
  year?: number | null;
  status?: string | null;
};

type BackendEpisode = {
  id: string;
  number: number;
  title?: string | null;
};

/**
 * Type guards to assert unknown data matches Backend DTO shape
 * These are used internally by mappers to safely cast API responses
 */

function isBackendAnime(data: unknown): data is BackendAnime {
  return typeof data === 'object' && data !== null && 'id' in data && 'title' in data;
}

function isBackendRelease(data: unknown): data is BackendRelease {
  return typeof data === 'object' && data !== null && 'id' in data && 'anime_id' in data;
}

function isBackendEpisode(data: unknown): data is BackendEpisode {
  return typeof data === 'object' && data !== null && 'id' in data && 'number' in data;
}

/**
 * Export type guards and DTO types for mapper-internal use only
 */
export type { 
  BackendAnime, 
  BackendRelease, 
  BackendEpisode
};

export {
  isBackendAnime,
  isBackendRelease,
  isBackendEpisode
};
