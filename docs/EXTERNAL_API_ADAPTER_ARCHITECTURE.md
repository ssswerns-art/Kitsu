# External API Adapter Layer — Architecture Documentation

## Overview

This document describes the External API Adapter Layer architecture implemented in the Kitsu frontend application. The adapter layer provides strict isolation between external API services (Shikimori, Kodik, AniList) and the application's query/mutation/UI layers.

## Architecture Principles

### 1. Complete Isolation
- **External APIs** (Shiki, Kodik, AniList, /api/* proxy) are ONLY accessible through adapter functions
- **Query/Mutation/UI layers** have ZERO knowledge of:
  - External API URLs or endpoints
  - HTTP client usage (axios, fetch)
  - Retry/fallback logic
  - External API response shapes or DTOs
  - Contract validation logic

### 2. Adapter Contract
```typescript
Input:  ONLY primitives (string, number, boolean) or domain IDs
Output: ONLY domain models from @/types/*
```

### 3. Type Safety
- Adapters export ONLY functions
- NO type exports (DTOs, response shapes, etc.)
- Attempting to import types from adapters → TypeScript compilation error

### 4. Error Handling
- All adapters use `withRetryAndFallback` + `EXTERNAL_API_POLICY`
- Contract validation happens INSIDE adapters
- All errors normalized to `BaseApiError` before leaving adapter
- Graceful degradation with fallback values

## Directory Structure

```
frontend/
├─ external/                    # External API Adapters (NEW)
│  ├─ proxy/
│  │  └─ proxy.adapter.ts      # Proxy API adapter (Shiki/Kodik)
│  └─ anilist/
│     └─ anilist.adapter.ts    # AniList GraphQL adapter
├─ lib/
│  ├─ adapter-guards.ts        # Runtime invariant guards (NEW)
│  ├─ api-retry.ts             # Retry policies (existing)
│  ├─ api-errors.ts            # Error taxonomy (existing)
│  └─ contract-guards.ts       # Contract validation (existing)
├─ query/                       # Query layer (REFACTORED)
│  ├─ get-anime-schedule.ts    # Uses proxy adapter
│  ├─ get-episode-data.ts      # Uses proxy adapter
│  ├─ get-episode-servers.ts   # Uses proxy adapter
│  └─ get-banner-anime.ts      # Uses anilist adapter
└─ mutation/                    # Mutation layer (REFACTORED)
   └─ get-anilist-animes.ts    # Uses anilist adapter
```

## Adapters

### Proxy API Adapter (`frontend/external/proxy/proxy.adapter.ts`)

Wraps all `/api/*` proxy endpoints (Shikimori, Kodik):

#### Functions:
1. **`fetchAnimeSchedule(date: string)`**
   - Endpoint: `/api/schedule`
   - Returns: `IAnimeSchedule`
   - Fallback: Empty schedule array

2. **`fetchEpisodeSources(episodeId: string, server: string | undefined, subOrDub: string)`**
   - Endpoint: `/api/episode/sources`
   - Returns: `IEpisodeSource`
   - Fallback: Empty sources

3. **`fetchEpisodeServers(episodeId: string)`**
   - Endpoint: `/api/episode/servers`
   - Returns: `IEpisodeServers`
   - Fallback: Empty servers

4. **`importAniListAnimes(animes: AniListMediaListInput[])`**
   - Endpoint: `/api/import/anilist`
   - Returns: `AniListImportResponseDomain`
   - Fallback: Empty array

#### Example Usage:
```typescript
// BEFORE (query layer had external API knowledge):
const res = await api.get("/api/schedule?date=" + date, { timeout: 10000 });
assertExternalApiShape(res.data, endpoint);
return res.data.data as IAnimeSchedule;

// AFTER (query layer is clean):
return fetchAnimeSchedule(date);
```

### AniList GraphQL Adapter (`frontend/external/anilist/anilist.adapter.ts`)

Wraps AniList GraphQL API:

#### Functions:
1. **`fetchAnimeBanner(anilistID: number)`**
   - Endpoint: `https://graphql.anilist.co`
   - Query: Media banner image
   - Returns: `AnimeBannerDomain`
   - Fallback: Empty banner

2. **`fetchUserAnimeList(username: string)`**
   - Endpoint: `https://graphql.anilist.co`
   - Query: User's anime list
   - Returns: `Data` (from @/types/anilist-animes)
   - Fallback: Empty list

#### Example Usage:
```typescript
// BEFORE (mutation layer had GraphQL knowledge):
const res = await api.post("https://graphql.anilist.co", {
  query: `query ($username: String) { ... }`,
  variables: { username }
});

// AFTER (mutation layer is clean):
return fetchUserAnimeList(username);
```

## Runtime Guardrails

### `adapter-guards.ts`

Provides runtime invariant enforcement:

```typescript
// Called at the start of every adapter function
assertIsExternalAdapterCall('AdapterName.functionName');

// Type marker for adapter return types
type AdapterDomainModel<T> = T;
```

## Internal vs External APIs

### External APIs (use adapters)
- `/api/schedule` → `fetchAnimeSchedule()`
- `/api/episode/sources` → `fetchEpisodeSources()`
- `/api/episode/servers` → `fetchEpisodeServers()`
- `/api/import/anilist` → `importAniListAnimes()`
- `https://graphql.anilist.co` → `fetchAnimeBanner()`, `fetchUserAnimeList()`

### Internal APIs (remain in query layer)
- `/anime` → query layer (INTERNAL_API_POLICY)
- `/search/anime` → query layer (INTERNAL_API_POLICY)
- `/releases` → query layer (INTERNAL_API_POLICY)
- `/episodes` → query layer (INTERNAL_API_POLICY)

**Rationale:** Internal Kitsu backend APIs are stable and controlled, use fail-fast policy (no retry, no fallback). External APIs are unreliable and require retry + fallback.

## Validation Checks

### Build-time Validation
```bash
# 1. TypeScript compilation
npm run build
# → ✓ Compiled successfully

# 2. Linting
npm run lint
# → ✔ No ESLint warnings or errors
```

### Runtime Validation
```bash
# 3. Axios imports (should be ONLY in lib/* and external/*)
grep -r "import.*axios" --include="*.ts" .
# → 5 matches (lib/api.ts, lib/auth-errors.ts, external/*)

# 4. External API calls in query/* (should be NONE)
grep -r "/api/\|graphql.anilist" query/
# → 0 matches

# 5. assertExternalApiShape in query/* (should be NONE)
grep -r "assertExternalApiShape" query/
# → 0 matches
```

## Migration Guide

### For Adding New External API

1. **Create Adapter File**
   ```typescript
   // frontend/external/newservice/newservice.adapter.ts
   export async function fetchData(id: string): Promise<DomainModel> {
     assertIsExternalAdapterCall('NewServiceAdapter.fetchData');
     const endpoint = "/api/newservice/data";
     const fallback: DomainModel = { /* empty */ };
     
     return withRetryAndFallback(
       async () => {
         const res = await api.get(endpoint, { params: { id } });
         assertExternalApiShape(res.data, endpoint);
         return res.data as DomainModel;
       },
       EXTERNAL_API_POLICY,
       endpoint,
       fallback
     );
   }
   ```

2. **Update Query Layer**
   ```typescript
   // frontend/query/get-newservice-data.ts
   import { fetchData } from "@/external/newservice/newservice.adapter";
   
   const getData = async (id: string) => {
     return fetchData(id); // No URLs, no axios, no retry logic
   };
   ```

3. **Validate**
   ```bash
   npm run build  # Must succeed
   npm run lint   # Must pass
   grep -r "newservice-endpoint" query/  # Must be empty
   ```

### For Removing External API

1. Delete adapter file: `external/service/service.adapter.ts`
2. Run `npm run build` → TypeScript will fail if query layer still references it
3. Update query layer to use alternative data source
4. Validate: `npm run build` → Must succeed

**Key Guarantee:** Removing an adapter CANNOT break TypeScript compilation if query layer is properly isolated.

## Benefits

### 1. Maintainability
- Changing external API URL → edit adapter only
- Switching from Kodik to different video provider → replace adapter, query layer untouched
- Adding retry logic → adapter only

### 2. Testability
- Mock adapters for testing query layer
- Test adapters in isolation with real API responses
- Test query layer without external API dependencies

### 3. Security
- Single point of external API access → easier to audit
- Contract validation centralized in adapters
- Runtime invariants prevent accidental leakage

### 4. Type Safety
- Query layer cannot accidentally import external DTOs
- Compile-time enforcement of adapter boundaries
- IDE autocomplete only shows domain models

## Acceptance Criteria ✅

- [x] External APIs fully isolated in `frontend/external/*`
- [x] Query layer clean and domain-focused
- [x] Architecture protected from regressions
- [x] TypeScript compilation enforces boundaries
- [x] Runtime invariants in place
- [x] Replacing/removing external API does NOT require query layer changes
- [x] All validation checks pass

## References

- Error Taxonomy: `frontend/lib/api-errors.ts`
- Retry Policies: `frontend/lib/api-retry.ts`
- Contract Guards: `frontend/lib/contract-guards.ts`
- Adapter Guards: `frontend/lib/adapter-guards.ts`
