"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuthSelector } from "@/store/auth-store";
import { getPlayerStorage, updatePlayerStorage } from "@/utils/player-storage";
import { convertFractionToPercent, parseNumber } from "@/utils/player-progress";
import { BackendWatchProgressDTO } from "@/mappers/common";
import { mapWatchProgress } from "@/mappers/watch.mapper";

type WatchProgressRequestPayload = {
  anime_id: string;
  episode: number;
  position_seconds?: number;
  progress_percent?: number;
};

export type WatchProgressPayload = {
  episode: number;
  translationKey?: string;
  positionSeconds?: number;
  progressPercent?: number;
};

export type WatchProgressState = WatchProgressPayload & {
  source: "server" | "local";
};

export type WatchProgressStatus = "idle" | "loading" | "loaded";

const DEFAULT_LIMIT = 100;

export const useWatchProgress = (animeId: string) => {
  const auth = useAuthSelector((state) => state.auth);
  const [progress, setProgress] = useState<WatchProgressState | null>(null);
  const [status, setStatus] = useState<WatchProgressStatus>("idle");
  const lastSyncedPayloadRef = useRef<WatchProgressRequestPayload | null>(null);

  const isAuthenticated = Boolean(auth?.accessToken);

  useEffect(() => {
    setProgress(null);
    setStatus("idle");
    lastSyncedPayloadRef.current = null;
  }, [animeId, isAuthenticated]);

  const loadProgress = useCallback(async () => {
    if (!animeId) return;
    setStatus("loading");
    const localSnapshot = getPlayerStorage(animeId);
    const localProgressPercent = convertFractionToPercent(
      parseNumber(localSnapshot.progressPercent),
    );
    const localProgress: WatchProgressState | null =
      typeof localSnapshot.lastEpisode === "number"
        ? {
            episode: localSnapshot.lastEpisode,
            translationKey: localSnapshot.lastTranslation,
            positionSeconds: localSnapshot.positionSeconds,
            progressPercent: localProgressPercent,
            source: "local",
          }
        : null;

    if (!isAuthenticated) {
      setProgress(localProgress);
      setStatus("loaded");
      return;
    }

    try {
      const response = await api.get<BackendWatchProgressDTO[]>("/watch/continue", {
        params: { limit: DEFAULT_LIMIT },
      });
      const backendMatch = (response.data || []).find(
        (item) => item.anime_id === animeId,
      );
      if (backendMatch) {
        const mapped = mapWatchProgress(backendMatch);
        const progressPercent = convertFractionToPercent(
          parseNumber(mapped.progressPercent),
        );
        const positionSeconds = parseNumber(mapped.positionSeconds);
        updatePlayerStorage(animeId, {
          lastEpisode: mapped.episode,
          positionSeconds,
          progressPercent,
          syncedToServer: true,
        });
        setProgress({
          episode: mapped.episode,
          translationKey: localSnapshot.lastTranslation,
          positionSeconds,
          progressPercent,
          source: "server",
        });
        setStatus("loaded");
        return;
      }

      const shouldMigrateLocal =
        !localSnapshot.syncedToServer &&
        typeof localSnapshot.lastEpisode === "number" &&
        (localSnapshot.positionSeconds !== undefined ||
          localProgressPercent !== undefined);

      if (shouldMigrateLocal) {
        const requestPayload: WatchProgressRequestPayload = {
          anime_id: animeId,
          episode: localSnapshot.lastEpisode!,
        };

        if (localSnapshot.positionSeconds !== undefined) {
          requestPayload.position_seconds = localSnapshot.positionSeconds;
        }

        if (localProgressPercent !== undefined) {
          requestPayload.progress_percent = localProgressPercent;
        }

        await api.post("/watch/progress", requestPayload);
        updatePlayerStorage(animeId, { syncedToServer: true });
        if (localProgress) {
          setProgress({ ...localProgress, source: "server" });
        }
        setStatus("loaded");
        return;
      }
    } catch (error) {
      console.error("Failed to load watch progress", error);
      setProgress(localProgress);
      setStatus("loaded");
      return;
    }

    setProgress(null);
    setStatus("loaded");
  }, [animeId, isAuthenticated]);

  const saveProgress = useCallback(
    async (payload: WatchProgressPayload) => {
      if (!animeId || !payload.episode) return;
      const progressPercent = convertFractionToPercent(payload.progressPercent);
      const positionSeconds = parseNumber(payload.positionSeconds);
      const nextTranslation = payload.translationKey;

      const storageUpdate = {
        lastEpisode: payload.episode,
        lastTranslation: nextTranslation,
        positionSeconds,
        progressPercent,
        ...(isAuthenticated ? { syncedToServer: true } : {}),
      };

      updatePlayerStorage(animeId, storageUpdate);

      if (!isAuthenticated) return;

      try {
        const requestPayload: WatchProgressRequestPayload = {
          anime_id: animeId,
          episode: payload.episode,
        };

        if (positionSeconds !== undefined) {
          requestPayload.position_seconds = positionSeconds;
        }

        if (progressPercent !== undefined) {
          requestPayload.progress_percent = progressPercent;
        }

        const lastPayload = lastSyncedPayloadRef.current;
        const hasPositionSeconds = Object.prototype.hasOwnProperty.call(
          requestPayload,
          "position_seconds",
        );
        const hasProgressPercent = Object.prototype.hasOwnProperty.call(
          requestPayload,
          "progress_percent",
        );
        const isDuplicatePayload =
          lastPayload?.anime_id === requestPayload.anime_id &&
          lastPayload?.episode === requestPayload.episode &&
          Object.prototype.hasOwnProperty.call(
            lastPayload ?? {},
            "position_seconds",
          ) === hasPositionSeconds &&
          Object.prototype.hasOwnProperty.call(
            lastPayload ?? {},
            "progress_percent",
          ) === hasProgressPercent &&
          (!hasPositionSeconds ||
            lastPayload?.position_seconds === requestPayload.position_seconds) &&
          (!hasProgressPercent ||
            lastPayload?.progress_percent === requestPayload.progress_percent);
        if (isDuplicatePayload) return;
        lastSyncedPayloadRef.current = requestPayload;
        await api.post("/watch/progress", requestPayload);
      } catch (error) {
        console.error("Failed to sync watch progress", error);
      }
    },
    [animeId, isAuthenticated],
  );

  const fallbackTranslation = getPlayerStorage(animeId).lastTranslation;

  return {
    progress,
    status,
    loadProgress,
    saveProgress,
    fallbackTranslation,
  };
};
