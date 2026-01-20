/**
 * Anime mappers - converts backend DTOs to frontend models
 * Pure functions with strict validation
 */

import {
  IAnime,
  LatestCompletedAnime,
  SpotlightAnime,
  TopUpcomingAnime,
  ISuggestionAnime,
  Type,
} from "@/types/anime";
import {
  Info,
  Season,
  MostPopularAnime,
  RelatedAnime,
  RecommendedAnime,
} from "@/types/anime-details";
import { BackendAnimeDTO, BackendReleaseDTO, requireString, mapStatusToType } from "./common";
import { PLACEHOLDER_POSTER } from "@/utils/constants";

/**
 * Maps backend anime DTO to frontend IAnime model
 * @throws Error if required fields are missing
 */
export function mapAnime(dto: BackendAnimeDTO): IAnime {
  const id = requireString(dto.id, "Anime.id");
  const title = requireString(dto.title, "Anime.title");

  return {
    id,
    name: title,
    jname: dto.title_original || title,
    poster: PLACEHOLDER_POSTER,
    episodes: { sub: null, dub: null },
    type: mapStatusToType(dto.status),
    rank: undefined,
  };
}

/**
 * Maps array of backend anime DTOs to frontend IAnime models
 */
export function mapAnimeList(dtos: BackendAnimeDTO[]): IAnime[] {
  return dtos.map(mapAnime);
}

/**
 * Maps backend anime DTO to LatestCompletedAnime
 * @throws Error if required fields are missing
 */
export function mapLatestCompletedAnime(dto: BackendAnimeDTO): LatestCompletedAnime {
  const base = mapAnime(dto);
  return {
    ...base,
    duration: "",
    rating: null,
  };
}

/**
 * Maps backend anime DTO to SpotlightAnime
 * @throws Error if required fields are missing
 */
export function mapSpotlightAnime(dto: BackendAnimeDTO, rank: number): SpotlightAnime {
  const id = requireString(dto.id, "SpotlightAnime.id");
  const title = requireString(dto.title, "SpotlightAnime.title");

  return {
    rank,
    id,
    name: title,
    description: dto.description || "",
    poster: PLACEHOLDER_POSTER,
    jname: dto.title_original || title,
    episodes: { sub: null, dub: null },
    type: mapStatusToType(dto.status) || Type.Tv,
    otherInfo: [],
  };
}

/**
 * Maps backend anime DTO to TopUpcomingAnime
 * @throws Error if required fields are missing
 */
export function mapTopUpcomingAnime(dto: BackendAnimeDTO): TopUpcomingAnime {
  const id = requireString(dto.id, "TopUpcomingAnime.id");
  const title = requireString(dto.title, "TopUpcomingAnime.title");

  return {
    id,
    name: title,
    jname: dto.title_original || title,
    poster: PLACEHOLDER_POSTER,
    duration: "",
    type: mapStatusToType(dto.status) || Type.Tv,
    rating: null,
    episodes: { sub: null, dub: null },
  };
}

/**
 * Maps backend anime DTO to ISuggestionAnime
 * @throws Error if required fields are missing
 */
export function mapSuggestionAnime(dto: BackendAnimeDTO): ISuggestionAnime {
  const base = mapAnime(dto);
  return {
    ...base,
    moreInfo: [],
  };
}

/**
 * Maps backend anime DTO to anime Info (for anime details)
 * @throws Error if required fields are missing
 */
export function mapAnimeInfo(dto: BackendAnimeDTO): Info {
  const id = requireString(dto.id, "AnimeInfo.id");
  const title = requireString(dto.title, "AnimeInfo.title");

  return {
    id,
    anilistId: 0,
    malId: 0,
    name: title,
    poster: PLACEHOLDER_POSTER,
    description: dto.description || "",
    stats: {
      rating: dto.status || "",
      quality: "",
      episodes: { sub: 0, dub: 0 },
      type: dto.status || "Unknown",
      duration: "",
    },
    promotionalVideos: [],
    charactersVoiceActors: [],
  };
}

/**
 * Maps backend release DTO to Season
 * @throws Error if required fields are missing
 */
export function mapSeason(dto: BackendReleaseDTO, isCurrent: boolean): Season {
  const id = requireString(dto.id, "Season.id");
  const title = requireString(dto.title, "Season.title");

  return {
    id,
    name: title,
    title,
    poster: PLACEHOLDER_POSTER,
    isCurrent,
  };
}

/**
 * Maps backend anime DTO to MostPopularAnime
 * @throws Error if required fields are missing
 */
export function mapMostPopularAnime(dto: BackendAnimeDTO): MostPopularAnime {
  const id = requireString(dto.id, "MostPopularAnime.id");
  const title = requireString(dto.title, "MostPopularAnime.title");

  return {
    id,
    name: title,
    jname: dto.title_original || title,
    poster: PLACEHOLDER_POSTER,
    episodes: { sub: 0, dub: 0 },
    type: dto.status || "Unknown",
  };
}

/**
 * Maps backend anime DTO to RelatedAnime
 * @throws Error if required fields are missing
 */
export function mapRelatedAnime(dto: BackendAnimeDTO): RelatedAnime {
  const id = requireString(dto.id, "RelatedAnime.id");
  const title = requireString(dto.title, "RelatedAnime.title");

  return {
    id,
    name: title,
    jname: dto.title_original || title,
    poster: PLACEHOLDER_POSTER,
    episodes: { sub: 0, dub: 0 },
    type: dto.status || "Unknown",
  };
}

/**
 * Maps backend anime DTO to RecommendedAnime
 * @throws Error if required fields are missing
 */
export function mapRecommendedAnime(dto: BackendAnimeDTO): RecommendedAnime {
  const id = requireString(dto.id, "RecommendedAnime.id");
  const title = requireString(dto.title, "RecommendedAnime.title");

  return {
    id,
    name: title,
    jname: dto.title_original || title,
    poster: PLACEHOLDER_POSTER,
    duration: "",
    type: dto.status || "Unknown",
    rating: undefined,
    episodes: { sub: 0, dub: 0 },
  };
}
