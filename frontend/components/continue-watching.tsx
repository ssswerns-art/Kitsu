"use client";

import React, { useCallback, useEffect, useState } from "react";
import Container from "./container";
import AnimeCard from "./anime-card";
import { ROUTES } from "@/constants/routes";
import BlurFade from "./ui/blur-fade";
import { History } from "lucide-react";
import { useAuthSelector } from "@/store/auth-store";
import { api } from "@/lib/api";
import { PLACEHOLDER_POSTER } from "@/utils/constants";
import { getLocalStorageJSON, removeLocalStorageItem } from "@/utils/storage";
import { getPlayerStorage } from "@/utils/player-storage";
import {
  COMPLETED_PROGRESS_MIN,
  CONTINUE_PROGRESS_MAX,
  CONTINUE_PROGRESS_MIN,
  convertFractionToPercent,
  parseNumber,
} from "@/utils/player-progress";
import { BackendWatchProgressDTO, BackendAnimeDTO } from "@/mappers/common";
import { mapWatchProgress } from "@/mappers/watch.mapper";

type ContinueWatchingItem = {
  id: string;
  title: string;
  poster: string;
  episode: number;
  progressPercent: number;
  isCompleted: boolean;
};

const MOBILE_LIMIT = 4;
const DESKTOP_LIMIT = 8;
const MOBILE_QUERY = "(max-width: 640px)";

const resolveProgress = (value: unknown) => {
  const normalized = convertFractionToPercent(parseNumber(value));
  if (normalized !== undefined && normalized >= COMPLETED_PROGRESS_MIN) {
    return { isCompleted: true, progressPercent: CONTINUE_PROGRESS_MAX };
  }
  const clamped = Math.min(
    Math.max(normalized ?? CONTINUE_PROGRESS_MIN, CONTINUE_PROGRESS_MIN),
    CONTINUE_PROGRESS_MAX,
  );
  return { isCompleted: false, progressPercent: clamped };
};

const ContinueWatching = () => {
  const [anime, setAnime] = useState<ContinueWatchingItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [displayLimit, setDisplayLimit] = useState(DESKTOP_LIMIT);

  const auth = useAuthSelector((state) => state.auth);
  const isAuthenticated = Boolean(auth?.accessToken);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mediaQuery = window.matchMedia(MOBILE_QUERY);
    const updateLimit = () =>
      setDisplayLimit(mediaQuery.matches ? MOBILE_LIMIT : DESKTOP_LIMIT);
    updateLimit();
    mediaQuery.addEventListener("change", updateLimit);
    return () => mediaQuery.removeEventListener("change", updateLimit);
  }, []);

  const loadContinueWatching = useCallback(
    async (shouldPreserve = false) => {
      if (typeof window === "undefined") return;
      let resolved: ContinueWatchingItem[] = [];
      if (!shouldPreserve) {
        setAnime([]);
      }
      setIsLoading(true);

      if (isAuthenticated) {
        try {
          const response = await api.get<BackendWatchProgressDTO[]>(
            "/watch/continue",
            { params: { limit: displayLimit } },
          );
          const items = response.data || [];
          const detailed = await Promise.all(
            items.map(async (item) => {
              try {
                const mapped = mapWatchProgress(item);
                const animeResponse = await api.get<BackendAnimeDTO>(
                  `/anime/${mapped.animeId}`,
                );
                return { mapped, anime: animeResponse.data };
              } catch (error) {
                console.error("Failed to load anime details", error);
                const mapped = mapWatchProgress(item);
                return { mapped, anime: null };
              }
            }),
          );

          resolved = detailed.map(({ mapped, anime }) => {
            const { progressPercent, isCompleted } = resolveProgress(
              mapped.progressPercent,
            );
            return {
              id: mapped.animeId,
              title: anime?.title || "",
              poster: anime?.poster || PLACEHOLDER_POSTER,
              episode: mapped.episode,
              progressPercent,
              isCompleted,
            };
          });
        } catch (error) {
          console.error("Failed to load continue watching", error);
          resolved = [];
        }
      } else {
        const watchedAnimes: {
          anime: { id: string; title: string; poster: string };
          episodes: string[];
        }[] = getLocalStorageJSON("watched", []);

        if (!Array.isArray(watchedAnimes)) {
          removeLocalStorageItem("watched");
          resolved = [];
        } else {
          resolved = [...watchedAnimes]
            .reverse()
            .slice(0, displayLimit)
            .map((ani) => {
              const lastEpisode =
                ani.episodes.length > 0
                  ? ani.episodes[ani.episodes.length - 1]
                  : undefined;
              const episodeNumber = parseNumber(lastEpisode);
              if (!episodeNumber) return null;
              const { progressPercent, isCompleted } = resolveProgress(
                getPlayerStorage(ani.anime.id).progressPercent,
              );
              return {
                id: ani.anime.id,
                title: ani.anime.title,
                poster: ani.anime.poster,
                episode: episodeNumber,
                progressPercent,
                isCompleted,
              };
            })
            .filter(Boolean) as ContinueWatchingItem[];
        }
      }

      setAnime(resolved);
      setIsLoading(false);
    },
    [displayLimit, isAuthenticated],
  );

  useEffect(() => {
    void loadContinueWatching();
  }, [loadContinueWatching]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!isAuthenticated) return;
    const handleFocus = () => {
      void loadContinueWatching(true);
    };
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [isAuthenticated, loadContinueWatching]);

  if (isLoading && !anime.length) return null;
  if (!anime.length) return null;

  return (
    <Container className="flex flex-col gap-5 py-10 items-center lg:items-start">
      <div className="flex items-center gap-2">
        <History />
        <h5 className="text-2xl font-bold">Continue Watching</h5>
      </div>
      <div className="grid lg:grid-cols-5 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-7 w-full gap-5 content-center">
        {anime?.map(
          (ani, idx) =>
            ani.episode && (
              <BlurFade key={ani.id ?? idx} delay={idx * 0.05} inView>
                <AnimeCard
                  title={ani.title}
                  poster={ani.poster}
                  className="self-center justify-self-center"
                  href={`${ROUTES.ANIME_DETAILS}/${ani.id}`}
                  watchDetail={null}
                  continueWatching={{
                    episode: ani.episode,
                    progressPercent: ani.progressPercent,
                    isCompleted: ani.isCompleted,
                  }}
                />
              </BlurFade>
            ),
        )}
      </div>
    </Container>
  );
};

export default ContinueWatching;
