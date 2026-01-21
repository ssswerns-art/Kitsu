import React from "react";
import Link from "next/link";
import Image from "next/image";

import { cn, formatSecondsToMMSS } from "@/lib/utils";
import { Badge } from "./ui/badge";
import { buttonVariants } from "./ui/button";
import { Captions, Mic, Star } from "lucide-react";
import { WatchHistory } from "@/hooks/use-get-bookmark";
import { Progress } from "./ui/progress";

type Props = {
  className?: string;
  poster: string;
  title: string;
  episodeCard?: boolean;
  sub?: number | null;
  dub?: number | null;
  subTitle?: string;
  displayDetails?: boolean;
  variant?: "sm" | "lg";
  href?: string;
  showGenre?: boolean;
  watchDetail?: WatchHistory | null;
  continueWatching?: {
    episode: number;
    progressPercent: number;
    isCompleted: boolean;
  } | null;
  rating?: number | null;
  isNew?: boolean;
  isOngoing?: boolean;
};

const AnimeCard = ({
  displayDetails = true,
  // showGenre = true,
  variant = "sm",
  ...props
}: Props) => {
  const safeCurrent =
    typeof props.watchDetail?.current === "number"
      ? props.watchDetail.current
      : 0;
  const safeTotal =
    typeof props.watchDetail?.timestamp === "number" &&
    props.watchDetail.timestamp > 0
      ? props.watchDetail.timestamp
      : 0;

  const clampedCurrent = Math.min(safeCurrent, safeTotal);

  const percentage = safeTotal > 0 ? (clampedCurrent / safeTotal) * 100 : 0;
  const continueWatching = props.continueWatching;

  return (
    <Link href={props.href as string}>
      <div
        className={cn([
          "rounded-xl overflow-hidden relative cursor-pointer group",
          "transition-all duration-300 ease-out",
          "hover:scale-105 hover:-translate-y-2",
          "hover:shadow-2xl hover:shadow-primary/20",
          variant === "sm" &&
            "h-[12rem] min-[320px]:h-[16.625rem] sm:h-[18rem] max-w-[12.625rem] md:min-w-[12rem]",
          variant === "lg" &&
            "max-w-[12.625rem] md:max-w-[18.75rem] h-auto md:h-[25rem] shrink-0 lg:w-[18.75rem]",
          props.className,
        ])}
      >
        {/* Image with aspect ratio 2:3 */}
        <div className="relative w-full h-full">
          <Image
            src={props.poster}
            alt={props.title}
            fill
            className="object-cover transition-transform duration-500 group-hover:scale-110"
            unoptimized
          />
          
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-80 group-hover:opacity-100 transition-opacity duration-300"></div>
          
          {/* Badges at top */}
          <div className="absolute top-2 left-2 flex flex-wrap gap-1.5 z-10">
            {props.isNew && (
              <Badge className="bg-primary text-primary-foreground text-xs font-semibold px-2 py-0.5">
                Новинка
              </Badge>
            )}
            {props.isOngoing && (
              <Badge className="bg-green-500 text-white text-xs font-semibold px-2 py-0.5">
                Онгоинг
              </Badge>
            )}
          </div>

          {/* Rating */}
          {props.rating && (
            <div className="absolute top-2 right-2 flex items-center gap-1 bg-black/60 backdrop-blur-sm rounded-full px-2 py-1 z-10">
              <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
              <span className="text-xs font-semibold text-white">{props.rating.toFixed(1)}</span>
            </div>
          )}
        </div>

        {displayDetails && (
          <>
            <div className="absolute bottom-0 w-full flex flex-col gap-1 px-3 pb-3 z-10">
              <h5 className="line-clamp-2 font-semibold text-sm leading-tight drop-shadow-md">
                {props.title}
              </h5>
              {continueWatching ? (
                <div className="flex flex-col gap-1">
                  <p className="text-xs text-gray-300">
                    Серия {continueWatching.episode}
                  </p>
                  {continueWatching.isCompleted ? (
                    <span className="text-xs font-semibold text-emerald-400">
                      Completed
                    </span>
                  ) : (
                    <Progress value={continueWatching.progressPercent} className="h-1" />
                  )}
                  <span
                    className={cn(
                      buttonVariants({ variant: "default", size: "sm" }),
                      "mt-1 w-fit text-xs pointer-events-none bg-primary hover:bg-primary/90",
                    )}
                  >
                    Продолжить
                  </span>
                </div>
              ) : (
                <>
                  {props.watchDetail && (
                    <>
                      <p className="text-xs text-gray-300">
                        Episode {props.watchDetail.episodeNumber} -{" "}
                        {formatSecondsToMMSS(props.watchDetail.current)} /{" "}
                        {formatSecondsToMMSS(props.watchDetail.timestamp)}
                      </p>
                      <Progress value={percentage} className="h-1" />
                    </>
                  )}
                  {props.episodeCard ? (
                    <div className="flex flex-row items-center space-x-1.5">
                      {props.sub && (
                        <Badge className="bg-primary/90 text-white flex flex-row items-center space-x-0.5 text-xs px-1.5 py-0">
                          <Captions size={14} />
                          <span>{props.sub}</span>
                        </Badge>
                      )}
                      {props.dub && (
                        <Badge className="bg-green-500/90 text-white flex flex-row items-center space-x-0.5 text-xs px-1.5 py-0">
                          <Mic size={14} />
                          <span>{props.dub}</span>
                        </Badge>
                      )}
                      <p className="text-xs text-gray-300 truncate">{props.subTitle}</p>
                    </div>
                  ) : (
                    <span className="text-xs text-gray-300">{props.subTitle}</span>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </Link>
  );
};

export default AnimeCard;
