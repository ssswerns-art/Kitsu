/**
 * Common types and utilities for API response mapping
 * This file contains backend DTO types (snake_case) and common mapping utilities
 */

import { Type } from "@/types/anime";

/**
 * Backend DTO: Anime from API (snake_case)
 */
export type BackendAnimeDTO = {
  id: string;
  title: string;
  title_original?: string | null;
  description?: string | null;
  year?: number | null;
  status?: string | null;
  poster?: string | null;
};

/**
 * Backend DTO: Release from API (snake_case)
 */
export type BackendReleaseDTO = {
  id: string;
  anime_id: string;
  title: string;
  year?: number | null;
  status?: string | null;
};

/**
 * Backend DTO: Episode from API (snake_case)
 */
export type BackendEpisodeDTO = {
  id: string;
  number: number;
  title?: string | null;
};

/**
 * Backend DTO: Favorite from API (snake_case)
 */
export type BackendFavoriteDTO = {
  id: string;
  anime_id: string;
  created_at?: string;
};

/**
 * Backend DTO: Watch Progress from API (snake_case)
 */
export type BackendWatchProgressDTO = {
  anime_id: string;
  episode: number;
  position_seconds?: number | null;
  progress_percent?: number | null;
};

/**
 * Maps backend status string to Type enum
 * @throws Error if status is required but invalid
 */
export function mapStatusToType(status?: string | null, required: boolean = false): Type | undefined {
  if (!status) {
    if (required) {
      throw new Error("Anime status is required but not provided");
    }
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
      if (required) {
        throw new Error(`Invalid anime status: ${status}`);
      }
      return undefined;
  }
}

/**
 * Validates that a required string field is present
 * @throws Error if field is missing or empty
 */
export function requireString(value: string | null | undefined, fieldName: string): string {
  if (!value || value.trim() === "") {
    throw new Error(`${fieldName} is required`);
  }
  return value;
}

/**
 * Validates that a required number field is present
 * @throws Error if field is missing
 */
export function requireNumber(value: number | null | undefined, fieldName: string): number {
  if (value === null || value === undefined) {
    throw new Error(`${fieldName} is required`);
  }
  return value;
}
