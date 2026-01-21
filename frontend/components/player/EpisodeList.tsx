"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Captions, Mic } from "lucide-react";
import { Episode, IEpisodes } from "@/types/episodes";
import Select, { ISelectOptions } from "@/components/common/select";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  COMPLETED_PROGRESS_MIN,
  CONTINUE_PROGRESS_MAX,
  CONTINUE_PROGRESS_MIN,
} from "@/utils/player-progress";

type Props = {
  title: string;
  subOrDub?: { sub: number; dub: number };
  episodes: IEpisodes;
  isLoading: boolean;
  selectedEpisodeId?: string;
  onSelectEpisode: (episodeId: string) => void;
  progressByEpisodeNumber?: Record<number, number>;
  newEpisodeNumber?: number;
};

const SKELETON_COUNT = 9;
const EPISODES_PER_GROUP = 50;
const LABELS = {
  newEpisode: "Новая серия",
  continueWatching: "Продолжить просмотр",
};

const EpisodeList = ({
  title,
  subOrDub,
  episodes,
  isLoading,
  selectedEpisodeId,
  onSelectEpisode,
  progressByEpisodeNumber,
  newEpisodeNumber,
}: Props) => {
  const [currentGroup, setCurrentGroup] = useState("");
  const [search, setSearch] = useState("");
  const [filteredEpisodes, setFilteredEpisodes] = useState<Episode[]>([]);
  const totalEpisodes = episodes?.totalEpisodes ?? 0;
  const episodeById = useMemo(() => {
    const map = new Map<string, Episode>();
    for (const episode of episodes.episodes) {
      map.set(episode.episodeId, episode);
    }
    return map;
  }, [episodes]);
  const getEpisodeGroupRange = useCallback(
    (episodeNumber: number) => {
      // Group episodes into ranges of EPISODES_PER_GROUP to power the selector.
      const start =
        Math.floor((episodeNumber - 1) / EPISODES_PER_GROUP) *
          EPISODES_PER_GROUP +
        1;
      const end = Math.min(
        start + EPISODES_PER_GROUP - 1,
        totalEpisodes,
      );
      return `${start} - ${end}`;
    },
    [totalEpisodes],
  );

  useEffect(() => {
    if (totalEpisodes <= 0 || currentGroup) return;
    setCurrentGroup(
      `1 - ${Math.min(EPISODES_PER_GROUP, totalEpisodes)}`,
    );
  }, [currentGroup, totalEpisodes]);

  useEffect(() => {
    if (totalEpisodes <= 0 || !selectedEpisodeId) return;
    const selected = episodeById.get(selectedEpisodeId);
    if (!selected) return;
    setCurrentGroup(getEpisodeGroupRange(selected.number));
  }, [episodeById, getEpisodeGroupRange, selectedEpisodeId, totalEpisodes]);

  useEffect(() => {
    if (!episodes || !currentGroup) return;
    const [start, end] = currentGroup.split(" - ").map(Number);
    let filtered = episodes.episodes.filter((_, index) => {
      return index >= start - 1 && index <= end - 1;
    });

    if (search) {
      filtered = filtered.filter((episode) =>
        episode.number.toString().toLowerCase().includes(search.toLowerCase()),
      );
    }

    setFilteredEpisodes(filtered);
  }, [episodes, currentGroup, search]);

  const handleSelectEpisode = useCallback(
    (episode: string) => {
      onSelectEpisode(episode);
    },
    [onSelectEpisode],
  );

  const handleOnSelectChange = (range: string) => {
    setCurrentGroup(range);
  };

  const groupOptions = (): ISelectOptions[] => {
    let start = 1;
    const end = totalEpisodes;
    const options: ISelectOptions[] = [];
    while (start <= end) {
      const range = `${start} - ${Math.min(
        start + EPISODES_PER_GROUP - 1,
        end,
      )}`;
      options.push({ label: range, value: range });
      start += EPISODES_PER_GROUP;
    }
    return options;
  };

  return (
    episodes && (
      <div className="col-span-1 flex w-full flex-col gap-5 overflow-hidden rounded-lg border border-slate-800/70 bg-slate-950/40 min-h-[20vh] sm:min-h-[30vh] md:min-h-[40vh] lg:min-h-[60vh] max-h-[500px]">
        <div className="h-fit bg-slate-900/80 px-4 py-3">
          <h3 className="text-base font-semibold text-slate-100">Episodes</h3>
          <span className="text-xs text-slate-400">{title}</span>
          <div className="mt-3 flex w-full flex-col items-center justify-between gap-2 sm:flex-row">
            <Input
              placeholder="Search Episode"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="w-full sm:w-1/2"
            />
            <Select
              value={currentGroup}
              placeholder={currentGroup}
              onChange={handleOnSelectChange}
              options={groupOptions()}
              className="w-full sm:w-1/2"
            />
          </div>
        </div>
        <div
          className={cn(
            "flex flex-row flex-wrap gap-2.5 overflow-x-auto px-3 pb-4 pt-2 md:flex-col md:flex-nowrap md:overflow-y-auto",
          )}
        >
          {filteredEpisodes.map((episode) => (
            <EpisodeListItem
              key={episode.episodeId}
              episode={episode}
              subOrDub={subOrDub}
              isActive={selectedEpisodeId === episode.episodeId}
              progressPercent={progressByEpisodeNumber?.[episode.number]}
              isNewEpisode={newEpisodeNumber === episode.number}
              onSelect={() => handleSelectEpisode(episode.episodeId)}
            />
          ))}
          {!filteredEpisodes.length && !isLoading && (
            <div className="flex w-full items-center justify-center rounded-md border border-dashed border-slate-800/70 bg-slate-900/40 px-4 py-6 text-xs text-slate-400">
              No episodes available.
            </div>
          )}
          {isLoading && <PlaylistSkeleton />}
        </div>
      </div>
    )
  );
};

type EpisodeItemProps = {
  episode: Episode;
  subOrDub?: { sub: number; dub: number };
  isActive: boolean;
  progressPercent?: number;
  isNewEpisode?: boolean;
  onSelect: () => void;
};

const EpisodeListItem = ({
  episode,
  subOrDub,
  isActive,
  progressPercent,
  isNewEpisode,
  onSelect,
}: EpisodeItemProps) => {
  const clampedProgress = Math.max(0, Math.min(progressPercent ?? 0, 100));
  const isContinue =
    clampedProgress >= CONTINUE_PROGRESS_MIN &&
    clampedProgress <= CONTINUE_PROGRESS_MAX;
  const isCompleted = clampedProgress >= COMPLETED_PROGRESS_MIN;
  const status = isActive
    ? "active"
    : isContinue
      ? "continue"
      : isNewEpisode
        ? "new"
        : isCompleted
          ? "completed"
          : "unwatched";

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex w-[8.5rem] flex-col gap-2 rounded-md border border-transparent px-3 py-2 text-sm transition-colors md:w-full",
        status === "active"
          ? "bg-[#e9376b] text-white ring-2 ring-pink-400/70 ring-offset-2 ring-offset-[#0f172a] shadow-lg border-pink-400/80"
          : status === "continue"
            ? "bg-slate-900/70 text-slate-100 border-pink-400/40 ring-1 ring-pink-400/60"
            : status === "new"
              ? "bg-slate-900/70 text-slate-100 border-amber-400/40"
              : status === "completed"
                ? "bg-slate-900 text-slate-200 border-emerald-400/30"
                : "bg-transparent text-slate-200 hover:bg-slate-800/70",
      )}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className="flex items-center gap-2 whitespace-nowrap">
          {`Episode ${episode.number}`}
          {status === "continue" && <span className="h-2 w-2 rounded-full bg-pink-400" />}
        </span>
        <div className="flex items-center gap-1">
          {subOrDub && episode.number <= subOrDub.sub && (
            <Captions className="text-gray-300" />
          )}
          {subOrDub && episode.number <= subOrDub.dub && (
            <Mic className="text-gray-300" />
          )}
        </div>
      </div>
      {status === "continue" && (
        <span className="w-fit rounded-full bg-pink-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-pink-200">
          {LABELS.continueWatching}
        </span>
      )}
      {status === "new" && (
        <span className="w-fit rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
          {LABELS.newEpisode} {episode.number}
        </span>
      )}
      {(status === "continue" || status === "completed") && (
        <div className="w-full">
          <div className="h-1 w-full overflow-hidden rounded-full bg-slate-800/70">
            <span
              className={cn(
                "block h-full rounded-full transition-all",
                status === "completed" ? "bg-emerald-400" : "bg-pink-400",
              )}
              style={{ width: `${status === "completed" ? 100 : clampedProgress}%` }}
            />
          </div>
        </div>
      )}
    </button>
  );
};

const PlaylistSkeleton = () => {
  return (
    <>
      {Array(SKELETON_COUNT)
        .fill(0)
        .map((_, idx) => (
          <div
            className="flex gap-5 items-center w-full min-h-16 rounded-md animate-pulse bg-slate-800"
            key={`skeleton-${idx}`}
          ></div>
        ))}
    </>
  );
};

export default EpisodeList;
