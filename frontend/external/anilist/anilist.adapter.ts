/**
 * AniList GraphQL Adapter — External API Isolation Layer
 * ========================================================
 * 
 * ARCHITECTURAL INVARIANTS:
 * 
 * 1. BOUNDARY ENFORCEMENT
 *    - This adapter is the ONLY place where AniList GraphQL is called
 *    - Query layer MUST NOT import axios, api, or call GraphQL directly
 *    - All AniList queries go through this adapter
 * 
 * 2. CONTRACT
 *    - Input: ONLY primitives (numbers for IDs, strings for usernames)
 *    - Output: ONLY domain models (simple objects with bannerImage)
 *    - NEVER expose GraphQL schema types or raw API response shapes
 * 
 * 3. ERROR HANDLING
 *    - Uses withRetryAndFallback from api-retry (EXTERNAL_API_POLICY)
 *    - Contract validation happens INSIDE adapter (assertExternalApiShape)
 *    - Errors are normalized to BaseApiError before leaving adapter
 * 
 * 4. TYPE ISOLATION
 *    - This module exports ONLY functions
 *    - NO type exports (GraphQL types, response shapes, etc.)
 *    - Query layer cannot accidentally import external contracts
 * 
 * EXTERNAL APIs WRAPPED:
 * - https://graphql.anilist.co - AniList GraphQL API
 * 
 * REMOVAL GUARANTEE:
 * Deleting this adapter should NOT break query layer TypeScript compilation.
 * Query layer only knows domain types, not GraphQL schema.
 */

import { api } from "@/lib/api";
import { assertExternalApiShape, assertFieldExists } from "@/lib/contract-guards";
import { withRetryAndFallback, EXTERNAL_API_POLICY } from "@/lib/api-retry";
import { normalizeToApiError } from "@/lib/api-errors";
import { assertIsExternalAdapterCall, type AdapterDomainModel } from "@/lib/adapter-guards";
import type { Data } from "@/types/anilist-animes";

/**
 * Domain model for anime banner
 * This is a local type, not exported, to prevent leakage
 */
interface AnimeBannerDomain {
  Media: {
    id: number;
    bannerImage: string;
  };
}

/**
 * Fetches anime banner image from AniList GraphQL API
 * 
 * ADAPTER CONTRACT:
 * - Input: anilistID (number primitive)
 * - Output: AnimeBannerDomain model
 * - Fallback: empty banner on failure (graceful degradation)
 * 
 * INVARIANTS:
 * - Uses EXTERNAL_API_POLICY (retry with backoff)
 * - Contract validation happens inside adapter
 * - Never throws raw errors (normalized to BaseApiError)
 * - GraphQL query is encapsulated (query layer doesn't know it exists)
 * 
 * @param anilistID - AniList media ID (primitive number)
 * @returns Promise<AnimeBannerDomain> - Domain model, never raw GraphQL response
 */
export async function fetchAnimeBanner(
  anilistID: number
): Promise<AdapterDomainModel<AnimeBannerDomain>> {
  assertIsExternalAdapterCall('AniListAdapter.fetchAnimeBanner');
  
  const endpoint = "https://graphql.anilist.co";
  
  const fallback: AnimeBannerDomain = {
    Media: {
      id: anilistID,
      bannerImage: "",
    },
  };

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.post(
          endpoint,
          {
            query: `
              query ($id: Int) {
                Media(id: $id, type: ANIME) {
                  id
                  bannerImage
                }
              }
            `,
            variables: {
              id: anilistID,
            },
          },
          { timeout: 10000 }
        );
        
        // Contract validation - GraphQL external API, schema not guaranteed
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as AnimeBannerDomain;
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
 * Fetches user's anime list from AniList GraphQL API
 * 
 * ADAPTER CONTRACT:
 * - Input: username (string primitive)
 * - Output: Data domain model from @/types/anilist-animes
 * - Fallback: empty list on failure (graceful degradation)
 * 
 * INVARIANTS:
 * - Uses EXTERNAL_API_POLICY (retry with backoff)
 * - Contract validation happens inside adapter
 * - Never throws raw errors (normalized to BaseApiError)
 * - GraphQL query is encapsulated (mutation layer doesn't know it exists)
 * 
 * @param username - AniList username (primitive string)
 * @returns Promise<Data> - Domain model, never raw GraphQL response
 */
export async function fetchUserAnimeList(
  username: string
): Promise<AdapterDomainModel<Data>> {
  assertIsExternalAdapterCall('AniListAdapter.fetchUserAnimeList');
  
  const endpoint = "https://graphql.anilist.co";
  
  const fallback: Data = {
    MediaListCollection: {
      lists: [],
    },
  };

  return withRetryAndFallback(
    async () => {
      try {
        const res = await api.post(
          endpoint,
          {
            query: `
              query ($username: String) {
                MediaListCollection(type: ANIME, userName: $username) {
                  lists {
                    name
                    entries {
                      media {
                        id
                        bannerImage
                        idMal
                        title {
                          english
                        }
                      }
                    }
                    status
                  }
                }
              }
            `,
            variables: {
              username,
            },
          },
          { timeout: 10000 }
        );
        
        // Contract validation - GraphQL external API, schema not guaranteed
        assertExternalApiShape(res.data, endpoint);
        assertFieldExists(res.data, 'data', endpoint);
        
        return res.data.data as Data;
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
