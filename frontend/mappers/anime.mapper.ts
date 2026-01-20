import { 
  IAnime, 
  ISuggestionAnime, 
  SpotlightAnime, 
  TopUpcomingAnime,
  Type 
} from "@/types/anime";
import { Season } from "@/types/anime-details";
import { PLACEHOLDER_POSTER } from "@/utils/constants";
import { BackendAnime, BackendRelease } from "./common";
import { assertString, assertOptional } from "@/lib/contract-guards";

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
