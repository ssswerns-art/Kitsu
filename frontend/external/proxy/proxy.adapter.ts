/**
 * Proxy API Adapter — External API Isolation Layer
 * ==================================================
 * 
 * ARCHITECTURAL INVARIANTS:
 * 
 * 1. BOUNDARY ENFORCEMENT
 *    - This adapter is the ONLY place where /api/* endpoints are called
 *    - Query layer MUST NOT import axios, api, or call /api/* directly
 *    - All /api/* proxy calls (Shikimori, Kodik) go through this adapter
 * 
 * 2. CONTRACT
 *    - Input: ONLY primitives (strings, numbers, booleans)
 *    - Output: ONLY domain models from @/types/*
 *    - NEVER expose DTO types or raw API response shapes
 * 
 * 3. ERROR HANDLING
 *    - Uses withRetryAndFallback from api-retry (EXTERNAL_API_POLICY)
 *    - Contract validation happens INSIDE adapter (assertExternalApiShape)
 *    - Errors are normalized to BaseApiError before leaving adapter
 * 
 * 4. TYPE ISOLATION
 *    - This module exports ONLY functions
 *    - NO type exports (DTO, response shapes, etc.)
 *    - Query layer cannot accidentally import external contracts
 * 
 * EXTERNAL APIs WRAPPED:
 * - /api/schedule - Shikimori anime schedule
 * - /api/episode/sources - Kodik episode video sources
 * - /api/episode/servers - Kodik episode server list
 * 
 * REMOVAL GUARANTEE:
 * Deleting this adapter should NOT break query layer TypeScript compilation.
 * Query layer only knows domain types, not external API contracts.
 */

import { api } from "@/lib/api";
import { assertExternalApiShape, assertFieldExists } from "@/lib/contract-guards";
import { withRetryAndFallback, EXTERNAL_API_POLICY } from "@/lib/api-retry";
import { normalizeToApiError } from "@/lib/api-errors";
import { assertIsExternalAdapterCall, type AdapterDomainModel } from "@/lib/adapter-guards";
import type { IAnimeSchedule } from "@/types/anime-schedule";
import type { IEpisodeSource, IEpisodeServers } from "@/types/episodes";

/**
 * Domain model for AniList import response
 * This is a local type, not exported, to prevent leakage
 */
interface AniListImportResponseDomain {
  animes: Array<{
    id: string;
    title: string;
    thumbnail: string;
    status: string;
  }>;
}

/**
 * Domain model for AniList media list (input for import)
 * This is a local type, not exported, to prevent leakage
 */
interface AniListMediaListInput {
  name: string;
  entries: Array<{
    media: {
      id: number;
      bannerImage: string | null;
      idMal: number | null;
      title: {
        english: string | null;
      };
    };
  }>;
  status: string;
}

/**
 * Fetches anime schedule from Shikimori proxy
 * 
 * ADAPTER CONTRACT:
 * - Input: date string (primitive)
 * - Output: IAnimeSchedule domain model
 * - Fallback: empty schedule on failure (graceful degradation)
 * 
 * INVARIANTS:
 * - Uses EXTERNAL_API_POLICY (retry with backoff)
 * - Contract validation happens inside adapter
 * - Never throws raw errors (normalized to BaseApiError)
 * 
 * @param date - Date string for schedule query (e.g., "2024-01-20")
 * @returns Promise<IAnimeSchedule> - Domain model, never raw API response
 */
export async function fetchAnimeSchedule(
  date: string
): Promise<AdapterDomainModel<IAnimeSchedule>> {
  assertIsExternalAdapterCall('ProxyAdapter.fetchAnimeSchedule');
  
  const endpoint = "/api/schedule";
  const queryParams = date ? `?date=${date}` : "";
  
  const fallback: IAnimeSchedule = {
    scheduledAnimes: [],
  };

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.get(endpoint + queryParams, { timeout: 10000 });
        
        // Contract validation - external API, schema not guaranteed by backend
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as IAnimeSchedule;
      } catch (error) {
        // Normalize all errors to ApiError hierarchy
        throw normalizeToApiError(error, endpoint);
      }
    },
    EXTERNAL_API_POLICY,
    endpoint,
    fallback
  );
}

/**
 * Fetches episode video sources from Kodik proxy
 * 
 * ADAPTER CONTRACT:
 * - Input: episodeId (string), server (string | undefined), subOrDub (string)
 * - Output: IEpisodeSource domain model
 * - Fallback: empty source on failure (graceful degradation)
 * 
 * INVARIANTS:
 * - Uses EXTERNAL_API_POLICY (retry with backoff)
 * - Contract validation happens inside adapter
 * - Never throws raw errors (normalized to BaseApiError)
 * 
 * @param episodeId - Episode identifier
 * @param server - Server name (optional)
 * @param subOrDub - Audio category ("sub", "dub", or "raw")
 * @returns Promise<IEpisodeSource> - Domain model with video sources
 */
export async function fetchEpisodeSources(
  episodeId: string,
  server: string | undefined,
  subOrDub: string
): Promise<AdapterDomainModel<IEpisodeSource>> {
  assertIsExternalAdapterCall('ProxyAdapter.fetchEpisodeSources');
  
  const endpoint = "/api/episode/sources";
  
  const fallback: IEpisodeSource = {
    headers: { Referer: "" },
    tracks: [],
    intro: { start: 0, end: 0 },
    outro: { start: 0, end: 0 },
    sources: [],
    anilistID: 0,
    malID: 0,
  };

  if (!episodeId) return fallback;

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.get(endpoint, {
          params: {
            animeEpisodeId: decodeURIComponent(episodeId),
            server: server,
            category: subOrDub,
          },
          timeout: 10000,
        });
        
        // Contract validation - external API, schema not guaranteed by backend
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as IEpisodeSource;
      } catch (error) {
        // Normalize all errors to ApiError hierarchy
        throw normalizeToApiError(error, endpoint);
      }
    },
    EXTERNAL_API_POLICY,
    endpoint,
    fallback
  );
}

/**
 * Fetches available episode servers from Kodik proxy
 * 
 * ADAPTER CONTRACT:
 * - Input: episodeId (string)
 * - Output: IEpisodeServers domain model
 * - Fallback: empty servers on failure (graceful degradation)
 * 
 * INVARIANTS:
 * - Uses EXTERNAL_API_POLICY (retry with backoff)
 * - Contract validation happens inside adapter
 * - Never throws raw errors (normalized to BaseApiError)
 * 
 * @param episodeId - Episode identifier
 * @returns Promise<IEpisodeServers> - Domain model with server list
 */
export async function fetchEpisodeServers(
  episodeId: string
): Promise<AdapterDomainModel<IEpisodeServers>> {
  assertIsExternalAdapterCall('ProxyAdapter.fetchEpisodeServers');
  
  const endpoint = "/api/episode/servers";
  
  const fallback: IEpisodeServers = {
    episodeId: "",
    episodeNo: "",
    sub: [],
    dub: [],
    raw: [],
  };

  if (!episodeId) return fallback;

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.get(endpoint, {
          params: {
            animeEpisodeId: decodeURIComponent(episodeId),
          },
          timeout: 10000,
        });
        
        // Contract validation - external API, schema not guaranteed by backend
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as IEpisodeServers;
      } catch (error) {
        // Normalize all errors to ApiError hierarchy
        throw normalizeToApiError(error, endpoint);
      }
    },
    EXTERNAL_API_POLICY,
    endpoint,
    fallback
  );
}

/**
 * Imports AniList anime data through proxy
 * 
 * ADAPTER CONTRACT:
 * - Input: animes array (AniListMediaListInput[])
 * - Output: AniListImportResponseDomain with mapped anime data
 * - Fallback: empty array on failure (graceful degradation)
 * 
 * INVARIANTS:
 * - Uses EXTERNAL_API_POLICY (retry with backoff)
 * - Contract validation happens inside adapter
 * - Never throws raw errors (normalized to BaseApiError)
 * 
 * @param animes - Array of AniList media lists to import
 * @returns Promise<AniListImportResponseDomain> - Domain model with imported animes
 */
export async function importAniListAnimes(
  animes: AniListMediaListInput[]
): Promise<AdapterDomainModel<AniListImportResponseDomain>> {
  assertIsExternalAdapterCall('ProxyAdapter.importAniListAnimes');
  
  const endpoint = "/api/import/anilist";
  
  const fallback: AniListImportResponseDomain = {
    animes: [],
  };

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.post(endpoint, {
          animes,
        });
        
        // Contract validation - external API, schema not guaranteed by backend
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'animes', endpoint);
        
        return res.data as unknown as AniListImportResponseDomain;
      } catch (error) {
        // Normalize all errors to ApiError hierarchy
        throw normalizeToApiError(error, endpoint);
      }
    },
    EXTERNAL_API_POLICY,
    endpoint,
    fallback
  );
}

