"use client";

import { useMemo, useState } from "react";
import CalendarHeatmap from "react-calendar-heatmap";
import styles from "../heatmap.module.css";
import { Tooltip } from "react-tooltip";

type HeatmapValue = {
  date: string;
  count: number;
};

export type BookmarkData = {
  watchHistory: string[];
};

function AnimeHeatmap() {
  const heatmapData: HeatmapValue[] = [];
  const totalContributionCount = 0;

  const [baseDate] = useState(() => new Date("2024-01-01T00:00:00.000Z"));
  const dateOptions: Intl.DateTimeFormatOptions = {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  };
  const startDate = useMemo(() => {
    const date = new Date(baseDate);
    date.setUTCMonth(0, 1);
    return date;
  }, [baseDate]);
  const endDate = useMemo(() => {
    const date = new Date(baseDate);
    date.setUTCMonth(11, 31);
    return date;
  }, [baseDate]);

  const getClassForValue = (value: HeatmapValue | null): string => {
    if (!value || value.count === 0) {
      return styles.colorEmpty;
    }
    if (value.count >= 10) {
      return styles.colorScale4;
    }
    if (value.count >= 5) {
      return styles.colorScale3;
    }
    if (value.count >= 2) {
      return styles.colorScale2;
    }
    if (value.count >= 1) {
      return styles.colorScale1;
    }
    return styles.colorEmpty;
  };

  const getTooltipContent = (
    value: HeatmapValue | null,
  ): Record<string, string> => {
    const val = value as HeatmapValue;
    if (!val.date) {
      return {
        "data-tooltip-id": "heatmap-tooltip",
        "data-tooltip-content": "No episodes watched",
      };
    }
    const formatedDate = new Date(val.date).toLocaleDateString(
      "en-US",
      dateOptions,
    );
    return {
      "data-tooltip-id": "heatmap-tooltip",
      "data-tooltip-content": `Watched ${val.count} episodes on ${formatedDate}`,
    } as Record<string, string>;
  };

  return (
    <>
      <p className="text-lg font-bold mb-4">
        Watched {totalContributionCount} episodes in the last year
      </p>
      <CalendarHeatmap
        weekdayLabels={["", "M", "", "W", "", "F", ""]}
        showWeekdayLabels={true}
        showOutOfRangeDays={true}
        startDate={startDate}
        endDate={endDate}
        classForValue={(value) =>
          getClassForValue(value as unknown as HeatmapValue)
        }
        values={heatmapData}
        gutterSize={2}
        tooltipDataAttrs={(value) => getTooltipContent(value as HeatmapValue)}
      />
      <Tooltip id="heatmap-tooltip" />
    </>
  );
}

export default AnimeHeatmap;
