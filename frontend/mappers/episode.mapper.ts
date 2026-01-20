/**
 * Episode mappers - converts backend DTOs to frontend models
 * Pure functions with strict validation
 */

import { Episode } from "@/types/episodes";
import { BackendEpisodeDTO, requireString, requireNumber } from "./common";

/**
 * Maps backend episode DTO to frontend Episode model
 * @throws Error if required fields are missing
 */
export function mapEpisode(dto: BackendEpisodeDTO): Episode {
  const episodeId = requireString(dto.id, "Episode.id");
  const number = requireNumber(dto.number, "Episode.number");

  return {
    title: dto.title || `Episode ${number}`,
    episodeId,
    number,
    isFiller: false,
  };
}

/**
 * Maps array of backend episode DTOs to frontend Episode models
 */
export function mapEpisodeList(dtos: BackendEpisodeDTO[]): Episode[] {
  return dtos.map(mapEpisode);
}
