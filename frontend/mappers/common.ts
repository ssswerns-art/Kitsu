/**
 * Common Backend DTO Types
 * These represent the actual API response structure from backend (snake_case)
 */

export type BackendAnime = {
  id: string;
  title: string;
  title_original?: string | null;
  description?: string | null;
  year?: number | null;
  status?: string | null;
};

export type BackendRelease = {
  id: string;
  anime_id: string;
  title: string;
  year?: number | null;
  status?: string | null;
};

export type BackendEpisode = {
  id: string;
  number: number;
  title?: string | null;
};
