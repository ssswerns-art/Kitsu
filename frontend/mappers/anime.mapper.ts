import { 
  IAnime, 
  ISuggestionAnime, 
  SpotlightAnime, 
  TopUpcomingAnime,
  Type 
} from "@/types/anime";
import { Season } from "@/types/anime-details";
import { PLACEHOLDER_POSTER } from "@/utils/constants";
import { assertString, assertOptional, assertArray } from "@/lib/contract-guards";

/**
 * Backend DTO Types (INTERNAL - NOT EXPORTED)
 * These represent the actual API response structure from backend (snake_case)
 * 
 * ⚠️ CRITICAL: These types are private implementation details of this mapper.
 * They MUST NOT be exported or used outside this file.
 * Query layer works only with Domain Models (IAnime, Season, etc.)
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

/**
 * Type guards - internal helpers for safe casting from unknown
 */

function isBackendAnime(data: unknown): data is BackendAnime {
  return typeof data === 'object' && data !== null && 'id' in data && 'title' in data;
}

function isBackendRelease(data: unknown): data is BackendRelease {
  return typeof data === 'object' && data !== null && 'id' in data && 'anime_id' in data;
}

/**
 * Maps backend status string to frontend Type enum
 * Returns undefined for null/empty status or unknown values
 * PURE function - no optional chaining
 */
export function mapStatusToType(status?: string | null): Type | undefined {
  if (!status) {
    return undefined;
  }

  const normalizedStatus = status.toUpperCase();

  switch (normalizedStatus) {
    case "TV":
      return Type.Tv;
    case "ONA":
      return Type.Ona;
    case "MOVIE":
      return Type.Movie;
    default:
      return undefined;
  }
}

/**
 * Maps BackendAnime to IAnime
 * PURE function - no fallbacks, no optional chaining
 * Throws for required fields only
 */
export function mapBackendAnimeToIAnime(dto: BackendAnime): IAnime {
  assertString(dto.id, "Anime.id");
  assertString(dto.title, "Anime.title");

  const titleOriginal = assertOptional(dto.title_original, assertString, "Anime.title_original") ?? dto.title;

  return {
    id: dto.id,
    name: dto.title,
    jname: titleOriginal,
    poster: PLACEHOLDER_POSTER,
    episodes: { sub: null, dub: null },
    type: mapStatusToType(dto.status),
    rank: undefined,
  };
}

/**
 * Maps array of unknown data to IAnime array
 * This is the ONLY function that query layer should use for mapping anime arrays
 */
export function mapAnimeArrayToIAnimeArray(data: unknown): IAnime[] {
  assertArray(data, "AnimeArray");
  return data.map((item) => {
    if (!isBackendAnime(item)) {
      throw new Error("Invalid anime data in array");
    }
    return mapBackendAnimeToIAnime(item);
  });
}

/**
 * Maps BackendAnime to ISuggestionAnime
 * PURE function - no fallbacks, no optional chaining
 */
export function mapBackendAnimeToSuggestionAnime(dto: BackendAnime): ISuggestionAnime {
  assertString(dto.id, "Anime.id");
  assertString(dto.title, "Anime.title");

  const titleOriginal = assertOptional(dto.title_original, assertString, "Anime.title_original") ?? dto.title;

  return {
    id: dto.id,
    name: dto.title,
    jname: titleOriginal,
    poster: PLACEHOLDER_POSTER,
    episodes: { sub: null, dub: null },
    type: mapStatusToType(dto.status),
    rank: undefined,
    moreInfo: [],
  };
}

/**
 * Maps array of unknown data to ISuggestionAnime array
 */
export function mapAnimeArrayToSuggestionAnimeArray(data: unknown): ISuggestionAnime[] {
  assertArray(data, "AnimeArray");
  return data.map((item) => {
    if (!isBackendAnime(item)) {
      throw new Error("Invalid anime data in array");
    }
    return mapBackendAnimeToSuggestionAnime(item);
  });
}

/**
 * Maps BackendAnime to SpotlightAnime
 * PURE function - no fallbacks, no optional chaining
 * SpotlightAnime.type is required, so we throw if status is missing/invalid
 */
export function mapBackendAnimeToSpotlightAnime(dto: BackendAnime, rank: number): SpotlightAnime {
  assertString(dto.id, "Anime.id");
  assertString(dto.title, "Anime.title");
  
  const type = mapStatusToType(dto.status);
  if (!type) {
    throw new Error(`Invalid or missing anime status for SpotlightAnime: ${dto.status}`);
  }

  const titleOriginal = assertOptional(dto.title_original, assertString, "Anime.title_original") ?? dto.title;

  return {
    rank,
    id: dto.id,
    name: dto.title,
    description: "",
    poster: PLACEHOLDER_POSTER,
    jname: titleOriginal,
    episodes: { sub: null, dub: null },
    type,
    otherInfo: [],
  };
}

/**
 * Maps array of unknown data to SpotlightAnime array
 */
export function mapAnimeArrayToSpotlightAnimeArray(data: unknown): SpotlightAnime[] {
  assertArray(data, "AnimeArray");
  return data.map((item, idx) => {
    if (!isBackendAnime(item)) {
      throw new Error("Invalid anime data in array");
    }
    return mapBackendAnimeToSpotlightAnime(item, idx + 1);
  });
}

/**
 * Maps BackendAnime to TopUpcomingAnime
 * PURE function - no fallbacks, no optional chaining
 * TopUpcomingAnime.type is string, so we convert Type enum to string
 */
export function mapBackendAnimeToTopUpcomingAnime(dto: BackendAnime): TopUpcomingAnime {
  assertString(dto.id, "Anime.id");
  assertString(dto.title, "Anime.title");

  const type = mapStatusToType(dto.status);
  if (!type) {
    throw new Error(`Invalid or missing anime status for TopUpcomingAnime: ${dto.status}`);
  }

  const titleOriginal = assertOptional(dto.title_original, assertString, "Anime.title_original") ?? dto.title;

  return {
    id: dto.id,
    name: dto.title,
    jname: titleOriginal,
    poster: PLACEHOLDER_POSTER,
    duration: "",
    type: type as string,
    rating: null,
    episodes: { sub: null, dub: null },
  };
}

/**
 * Maps array of unknown data to TopUpcomingAnime array
 */
export function mapAnimeArrayToTopUpcomingAnimeArray(data: unknown): TopUpcomingAnime[] {
  assertArray(data, "AnimeArray");
  return data.map((item) => {
    if (!isBackendAnime(item)) {
      throw new Error("Invalid anime data in array");
    }
    return mapBackendAnimeToTopUpcomingAnime(item);
  });
}

/**
 * Maps BackendRelease to Season
 * PURE function - no fallbacks, no optional chaining
 */
export function mapBackendReleaseToSeason(dto: BackendRelease, isCurrent: boolean): Season {
  assertString(dto.id, "Release.id");
  assertString(dto.title, "Release.title");

  return {
    id: dto.id,
    name: dto.title,
    title: dto.title,
    poster: PLACEHOLDER_POSTER,
    isCurrent,
  };
}

/**
 * Maps unknown data to Season
 * This is the ONLY function that query layer should use for mapping single release
 */
export function mapReleaseToSeason(data: unknown, isCurrent: boolean): Season {
  if (!isBackendRelease(data)) {
    throw new Error("Invalid release data");
  }
  return mapBackendReleaseToSeason(data, isCurrent);
}

/**
 * Maps array of unknown data to Season array
 */
export function mapReleaseArrayToSeasonArray(data: unknown): Season[] {
  assertArray(data, "ReleaseArray");
  return data.map((item, idx) => {
    if (!isBackendRelease(item)) {
      throw new Error("Invalid release data in array");
    }
    return mapBackendReleaseToSeason(item, idx === 0);
  });
}
