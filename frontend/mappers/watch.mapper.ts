/**
 * Watch progress mappers - converts backend DTOs to frontend models
 * Pure functions with strict validation
 */

import { BackendWatchProgressDTO, BackendFavoriteDTO, requireString, requireNumber } from "./common";

/**
 * Mapped watch progress (frontend model)
 */
export type MappedWatchProgress = {
  animeId: string;
  episode: number;
  positionSeconds?: number;
  progressPercent?: number;
};

/**
 * Mapped favorite (frontend model)
 */
export type MappedFavorite = {
  id: string;
  animeId: string;
  createdAt?: string;
};

/**
 * Maps backend watch progress DTO to frontend model
 * @throws Error if required fields are missing
 */
export function mapWatchProgress(dto: BackendWatchProgressDTO): MappedWatchProgress {
  const animeId = requireString(dto.anime_id, "WatchProgress.anime_id");
  const episode = requireNumber(dto.episode, "WatchProgress.episode");

  return {
    animeId,
    episode,
    positionSeconds: dto.position_seconds !== null && dto.position_seconds !== undefined 
      ? dto.position_seconds 
      : undefined,
    progressPercent: dto.progress_percent !== null && dto.progress_percent !== undefined 
      ? dto.progress_percent 
      : undefined,
  };
}

/**
 * Maps array of backend watch progress DTOs to frontend models
 */
export function mapWatchProgressList(dtos: BackendWatchProgressDTO[]): MappedWatchProgress[] {
  return dtos.map(mapWatchProgress);
}

/**
 * Maps backend favorite DTO to frontend model
 * @throws Error if required fields are missing
 */
export function mapFavorite(dto: BackendFavoriteDTO): MappedFavorite {
  const id = requireString(dto.id, "Favorite.id");
  const animeId = requireString(dto.anime_id, "Favorite.anime_id");

  return {
    id,
    animeId,
    createdAt: dto.created_at,
  };
}

/**
 * Maps array of backend favorite DTOs to frontend models
 */
export function mapFavoriteList(dtos: BackendFavoriteDTO[]): MappedFavorite[] {
  return dtos.map(mapFavorite);
}
