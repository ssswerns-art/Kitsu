"use client";

import ContinueWatching from "@/components/continue-watching";
import FeaturedCollection from "@/components/featured-collection";
import { useGetHomePageData } from "@/query/get-home-page-data";
import { IAnime, LatestCompletedAnime, SpotlightAnime } from "@/types/anime";
import dynamic from "next/dynamic";
import { useEffect, useState, Suspense } from "react";
import { assertRenderMode } from "@/lib/render-mode";

// Dynamically import components
const HeroSection = dynamic(() => import("@/components/hero-section"));
const LatestEpisodesAnime = dynamic(
  () => import("@/components/latest-episodes-section"),
);
const AnimeSchedule = dynamic(() => import("@/components/anime-schedule"));
const AnimeSections = dynamic(() => import("@/components/anime-sections"));

/**
 * Data fetching component wrapped in Suspense boundary
 * 
 * INVARIANTS:
 * - All data fetching happens here
 * - Parent component does not fetch data
 * - This component is wrapped in Suspense
 */
function HomePageContent() {
  const [shouldLoadHomeData, setShouldLoadHomeData] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return; // Skip during SSR
    const trigger = () => setShouldLoadHomeData(true);
    const timeoutId = window.setTimeout(trigger, 100);
    return () => window.clearTimeout(timeoutId);
  }, []);

  const { data, isLoading } = useGetHomePageData({
    enabled: shouldLoadHomeData,
  });
  const isHomeDataPending = !shouldLoadHomeData || isLoading || !data;

  return (
    <>
      <ContinueWatching />
      <HeroSection
        spotlightAnime={data?.spotlightAnimes as SpotlightAnime[]}
        isDataLoading={isHomeDataPending}
      />
      <LatestEpisodesAnime
        loading={isHomeDataPending}
        latestEpisodes={data?.latestEpisodeAnimes as LatestCompletedAnime[]}
      />

      <FeaturedCollection
        loading={isHomeDataPending}
        featuredAnime={[
          {
            title: "Most Favorite Anime",
            anime: data?.mostFavoriteAnimes as IAnime[],
          },
          {
            title: "Most Popular Anime",
            anime: data?.mostPopularAnimes as IAnime[],
          },
          {
            title: "Latest Completed Anime",
            anime: data?.latestCompletedAnimes as LatestCompletedAnime[],
          },
        ]}
      />
      <AnimeSections
        title={"Trending Anime"}
        trendingAnime={data?.trendingAnimes as IAnime[]}
        loading={isHomeDataPending}
      />

      <AnimeSchedule />

      <AnimeSections
        title={"Upcoming Animes"}
        trendingAnime={data?.topUpcomingAnimes as IAnime[]}
        loading={isHomeDataPending}
      />
    </>
  );
}

/**
 * Home page component
 * 
 * ARCHITECTURE:
 * - No data fetching in this component
 * - Data fetching is delegated to HomePageContent
 * - Suspense boundary wraps all data fetching
 * - Loading UI is handled by Suspense fallback
 */
export default function Home() {
  // Declare render mode - client component
  const RENDER_MODE = "client" as const;
  assertRenderMode(RENDER_MODE);
  
  return (
    <div className="flex flex-col bg-[#121212]">
      <Suspense fallback={<div className="min-h-screen" />}>
        <HomePageContent />
      </Suspense>
    </div>
  );
}
