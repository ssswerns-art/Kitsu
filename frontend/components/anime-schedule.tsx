"use client";

import Container from "./container";
import React, { useMemo } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { useGetAnimeSchedule } from "@/query/get-anime-schedule";
import Button from "./common/custom-button";
import Link from "next/link";
import { ROUTES } from "@/constants/routes";

function AnimeSchedule() {
  const [currentDate] = React.useState(
    () => new Date("2024-01-01T00:00:00.000Z"),
  );
  const currentDay = useMemo(
    () =>
      currentDate
        .toLocaleString("en-US", {
          weekday: "long",
          timeZone: "UTC",
        })
        .toLowerCase(),
    [currentDate],
  );
  const currentDayIndex = useMemo(
    () => currentDate.getUTCDay(),
    [currentDate],
  );
  const daysOfWeek = [
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
  ];
  const [currentSelectedTab, setCurrentSelectedTab] =
    React.useState<string>(currentDay);
  const defaultTab = daysOfWeek.includes(currentDay) ? currentDay : "monday";

  const selectedDate = useMemo(() => {
    const date = getDateForWeekday(currentSelectedTab);
    date.setUTCDate(date.getUTCDate() + 1);
    return date.toLocaleDateString("en-US", { timeZone: "UTC" });
  }, [currentSelectedTab, getDateForWeekday]);

  const [shouldLoadSchedule, setShouldLoadSchedule] =
    React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const id = window.requestAnimationFrame(() => setShouldLoadSchedule(true));
    return () => window.cancelAnimationFrame(id);
  }, []);

  const { isLoading, data } = useGetAnimeSchedule(selectedDate, {
    enabled: shouldLoadSchedule,
  });

  function getDateForWeekday(targetDay: string) {
    const targetIndex = daysOfWeek.indexOf(targetDay);
    const date = new Date(currentDate);
    const diff = targetIndex - currentDayIndex;
    date.setUTCDate(currentDate.getUTCDate() + diff);
    return date;
  }

  return (
    <Container className="flex flex-col gap-5 py-10 items-center lg:items-start">
      <h5 className="text-2xl font-bold">Schedule</h5>
      <Tabs
        orientation="vertical"
        defaultValue={defaultTab}
        onValueChange={(val) => setCurrentSelectedTab(val)}
        value={currentSelectedTab}
        className="w-full"
      >
        <TabsList className="grid w-full grid-cols-7">
          {daysOfWeek.map((day) => (
            <TabsTrigger key={day} value={day}>
              {day.substring(0, 3).toUpperCase()} -{" "}
              {getDateForWeekday(day).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                timeZone: "UTC",
              })}
            </TabsTrigger>
          ))}
        </TabsList>

        {!shouldLoadSchedule || isLoading || !Array.isArray(data?.scheduledAnimes) ? (
          <LoadingSkeleton />
        ) : (
          daysOfWeek.map((day) => (
            <TabsContent key={day} value={day}>
              {day === currentSelectedTab && (
                <div className="flex flex-col gap-5 w-full p-4">
                  {data.scheduledAnimes.map((anime) => (
                    <div
                      key={anime.id}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center gap-x-5">
                        <h3 className="text-sm text-gray-300 font-semibold">
                          {new Date(anime.airingTimestamp).toLocaleTimeString(
                            "en-US",
                            {
                              hour: "numeric",
                              minute: "2-digit",
                              hour12: true,
                            },
                          )}
                        </h3>
                        <h3 className="text-sm font-semibold">{anime.name}</h3>
                      </div>
                      <Link href={`${ROUTES.ANIME_DETAILS}/${anime.id}`}>
                        <Button
                          className="w-[8rem] bg-[#e9376b] text-white hover:bg-[#e9376b]"
                          size="sm"
                        >
                          Episode {anime.episode}
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>
          ))
        )}
      </Tabs>
    </Container>
  );
}

const LoadingSkeleton = () => {
  return (
    <Container className="flex flex-col gap-5 py-10 items-center lg:items-start">
      <div className="h-14 w-full animate-pulse bg-slate-700"></div>
      <div className="h-14 w-full animate-pulse bg-slate-700"></div>
      <div className="h-14 w-full animate-pulse bg-slate-700"></div>
      <div className="h-14 w-full animate-pulse bg-slate-700"></div>
    </Container>
  );
};

export default AnimeSchedule;
