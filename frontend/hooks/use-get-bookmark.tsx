"use client";

import { useAuthSelector } from "@/store/auth-store";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { PLACEHOLDER_POSTER } from "@/utils/constants";
import { getLocalStorageJSON, setLocalStorageJSON } from "@/utils/storage";
import { BackendFavoriteDTO, BackendAnimeDTO } from "@/mappers/common";
import { mapFavorite } from "@/mappers/watch.mapper";

type Props = {
  animeID?: string;
  status?: string;
  page?: number;
  per_page?: number;
  populate?: boolean;
};

export type Bookmark = {
  id: string;
  user: string;
  animeId: string;
  thumbnail: string;
  animeTitle: string;
  status: string;
  created: string;
  expand: {
    watchHistory: WatchHistory[];
  };
};

export type WatchHistory = {
  id: string;
  current: number;
  timestamp: number;
  episodeId: string;
  episodeNumber: number;
  created: string;
};

function useBookMarks({
  animeID,
  status,
  page,
  per_page,
  populate = true,
}: Props) {
  const auth = useAuthSelector((state) => state.auth);
  const progressKey = "watch-progress";
  const [bookmarks, setBookmarks] = useState<Bookmark[] | null>(null);
  const [totalPages, setTotalPages] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [progressQueue, setProgressQueue] = useState<
    Array<{
      bookmarkId: string;
      watchedRecordId: string | null;
      updatedAt: number;
    }>
  >(() => getLocalStorageJSON(progressKey, []));

  const filterParts = [];

  if (animeID) {
    filterParts.push(`animeId='${animeID}'`);
  }

  if (status) {
    filterParts.push(`status='${status}'`);
  }

  const filters = filterParts.join(" && ");

  useEffect(() => {
    if (!populate) return;
    if (!auth) {
      setBookmarks(null);
      setIsLoading(false);
      return;
    }
    const getBookmarks = async () => {
      try {
        setIsLoading(true);
        const res = await api.get("/favorites", {
          params: { limit: per_page || 20, offset: ((page || 1) - 1) * (per_page || 20) },
        });
        const favorites = (res.data || []) as BackendFavoriteDTO[];

        const detailed = await Promise.all(
          favorites.map(async (fav) => {
            try {
              const mapped = mapFavorite(fav);
              const animeRes = await api.get<BackendAnimeDTO>(`/anime/${mapped.animeId}`);
              return { mapped, anime: animeRes.data };
            } catch {
              const mapped = mapFavorite(fav);
              return { mapped, anime: null };
            }
          }),
        );

        if (favorites.length > 0) {
          const mapped = detailed.map(({ mapped, anime }) => ({
            id: mapped.id,
            user: auth.id || "",
            animeId: mapped.animeId,
            thumbnail: anime?.poster || PLACEHOLDER_POSTER,
            animeTitle: anime?.title || "Favorite",
            status: "favorite",
            created: mapped.createdAt || "",
            expand: { watchHistory: [] as WatchHistory[] },
          }));
          setTotalPages(1);
          setBookmarks(mapped);
        } else {
          setBookmarks(null);
          setTotalPages(0);
        }
      } catch (error) {
        console.log(error);
        setBookmarks(null);
      }
      setIsLoading(false);
    };

    getBookmarks();
  }, [animeID, status, page, per_page, filters, auth, populate]);

  useEffect(() => {
    setLocalStorageJSON(progressKey, progressQueue);
  }, [progressKey, progressQueue]);

  const createOrUpdateBookMark = async (
    animeID: string,
    _animeTitle?: string,
    _animeThumbnail?: string,
    _status?: string,
    showToast: boolean = true,
  ): Promise<string | null> => {
    if (!auth) {
      return null;
    }
    try {
      const existing = bookmarks?.find((b) => b.animeId === animeID);
      if (existing) {
        if (showToast) {
          toast.success("Already in favorites", {
            style: { background: "green" },
          });
        }
        return existing.id;
      }
      const created = await api.post("/favorites", {
        anime_id: animeID,
      });
      if (showToast) {
        toast.success("Added to favorites", { style: { background: "green" } });
      }
      return (created.data as any)?.id || animeID;
    } catch (error) {
      console.log(error);
      return null;
    }
  };

  const syncWatchProgress = async (
    bookmarkId: string | null,
    watchedRecordId: string | null,
    _episodeData?: unknown,
  ): Promise<string | null> => {
    void _episodeData;
    if (!bookmarkId) return watchedRecordId;

    const updatedRecordId = watchedRecordId || `${bookmarkId}-local`;
    setProgressQueue((existing) => {
      const filtered = existing.filter((entry) => entry.bookmarkId !== bookmarkId);
      filtered.push({
        bookmarkId,
        watchedRecordId: updatedRecordId,
        updatedAt: Date.now(),
      });
      return filtered;
    });

    return updatedRecordId;
  };

  return {
    bookmarks,
    syncWatchProgress,
    createOrUpdateBookMark,
    totalPages,
    isLoading,
  };
}

export default useBookMarks;
