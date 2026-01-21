"use client";
import { useEffect, useRef, useState } from "react";
import Image from "next/image";

import Container from "@/components/container";
import AnimeCard from "@/components/anime-card";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { IAnime } from "@/types/anime";
import AnimeCarousel from "@/components/anime-carousel";
import CharacterCard from "@/components/common/character-card";
import { ROUTES } from "@/constants/routes";
import PlayerShell from "@/components/player/PlayerShell";
import { Heart } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useGetAnimeDetails } from "@/query/get-anime-details";
import { useGetAllEpisodes } from "@/query/get-all-episodes";
import Loading from "@/app/loading";
import { useAuthSelector } from "@/store/auth-store";
import { useAnimeSelector } from "@/store/anime-store";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { usePermissions } from "@/auth/rbac";

const Page = () => {
  const { slug } = useParams();
  const slugParam = Array.isArray(slug) ? slug[0] : slug;
  const { data: anime, isLoading } = useGetAnimeDetails(slugParam ?? "");
  const animeId = anime?.anime.info.id ?? slugParam ?? "";
  const { data: episodesData, isLoading: episodesLoading } =
    useGetAllEpisodes(animeId);
  const auth = useAuthSelector((state) => state.auth);
  const setAnime = useAnimeSelector((state) => state.setAnime);
  const selectedEpisode = useAnimeSelector((state) => state.selectedEpisode);
  const setSelectedEpisode = useAnimeSelector(
    (state) => state.setSelectedEpisode,
  );
  const router = useRouter();
  const searchParams = useSearchParams();
  const episodeParam = searchParams.get("episode");
  const initialTypeParamRef = useRef(searchParams.get("type"));
  const hasResolvedTypeParamRef = useRef(false);
  const invalidEpisodeParamRef = useRef<string | null>(null);
  const skipUrlSyncForInvalidParamRef = useRef(false);
  const syncingFromUrlRef = useRef(false);
  const hasEpisodes = (episodesData?.episodes?.length ?? 0) > 0;
  const shouldRenderPlayer = episodesLoading || hasEpisodes;
  const hasRecommendations = Boolean(
    anime?.relatedAnimes.length || anime?.recommendedAnimes.length,
  );
  const permissions = usePermissions();
  const canWriteContent = permissions.includes("write:content");
  // RBAC NOTE:
  // write:content — visibility only (P1.4)
  // enforcement planned in P2
  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteId, setFavoriteId] = useState<string | null>(null);
  const [favoriteLoading, setFavoriteLoading] = useState(false);

  useEffect(() => {
    const loadFavorites = async () => {
      if (!auth || !slugParam) return;
      const res = await api.get("/favorites");
      const match = (res.data as any[])?.find(
        (fav) => fav.anime_id === slugParam,
      );
      if (match) {
        setIsFavorite(true);
        setFavoriteId(match.id);
      } else {
        setIsFavorite(false);
        setFavoriteId(null);
      }
    };
    loadFavorites();
  }, [auth, slugParam]);

  useEffect(() => {
    if (!anime) return;
    setAnime(anime);
  }, [anime, setAnime]);

  useEffect(() => {
    if (!episodesData?.episodes.length) return;
    const resolvedEpisode = (() => {
      if (!episodeParam) return undefined;
      const parsedEpisode = Number(episodeParam);
      if (Number.isNaN(parsedEpisode)) {
        return episodesData.episodes.find(
          (episode) => episode.episodeId === episodeParam,
        );
      }
      if (Number.isInteger(parsedEpisode) && parsedEpisode > 0) {
        return episodesData.episodes.find(
          (episode) => episode.number === parsedEpisode,
        );
      }
      return undefined;
    })();

    if (resolvedEpisode) {
      invalidEpisodeParamRef.current = null;
      if (resolvedEpisode.episodeId !== selectedEpisode) {
        syncingFromUrlRef.current = true;
        setSelectedEpisode(resolvedEpisode.episodeId);
      }
      return;
    }

    if (episodeParam) {
      if (invalidEpisodeParamRef.current !== episodeParam) {
        invalidEpisodeParamRef.current = episodeParam;
        // Preserve invalid URL episode so resume logic can select fallback without replacing the URL.
        skipUrlSyncForInvalidParamRef.current = true;
      }
      return;
    }

    invalidEpisodeParamRef.current = null;
    if (initialTypeParamRef.current && !hasResolvedTypeParamRef.current) {
      const latestEpisodeFromTypeParam =
        episodesData.episodes[episodesData.episodes.length - 1];
      if (
        latestEpisodeFromTypeParam &&
        latestEpisodeFromTypeParam.episodeId !== selectedEpisode
      ) {
        setSelectedEpisode(latestEpisodeFromTypeParam.episodeId);
      }
      hasResolvedTypeParamRef.current = true;
    }
  }, [episodesData, episodeParam, selectedEpisode, setSelectedEpisode]);

  useEffect(() => {
    if (!selectedEpisode) return;
    const selectedEpisodeNumber = episodesData?.episodes.find(
      (episode) => episode.episodeId === selectedEpisode,
    )?.number;
    if (selectedEpisodeNumber === undefined) return;
    const params = new URLSearchParams(searchParams.toString());
    const selectedEpisodeParam = String(selectedEpisodeNumber);
    const isEpisodeParamSynced = params.get("episode") === selectedEpisodeParam;
    if (syncingFromUrlRef.current) {
      syncingFromUrlRef.current = false;
      return;
    }
    if (isEpisodeParamSynced) {
      return;
    }
    if (skipUrlSyncForInvalidParamRef.current) {
      skipUrlSyncForInvalidParamRef.current = false;
      return;
    }
    if (!slugParam) return;
    params.set("episode", selectedEpisodeParam);
    router.replace(`${ROUTES.ANIME_DETAILS}/${slugParam}?${params.toString()}`, {
      scroll: false,
    });
  }, [episodesData, router, searchParams, selectedEpisode, slugParam]);

  const toggleFavorite = async () => {
    if (!auth) {
      toast.error("Please login to manage favorites", {
        style: { background: "red" },
      });
      return;
    }
    if (!slugParam) return;
    setFavoriteLoading(true);
    if (isFavorite && favoriteId) {
      await api.delete(`/favorites/${favoriteId}`);
      setIsFavorite(false);
      setFavoriteId(null);
      toast.success("Removed from favorites", {
        style: { background: "green" },
      });
    } else {
      const res = await api.post("/favorites", { anime_id: slugParam });
      setIsFavorite(true);
      setFavoriteId((res.data as any).id);
      toast.success("Added to favorites", { style: { background: "green" } });
    }
    setFavoriteLoading(false);
  };

  return isLoading || !anime ? (
    <Loading />
  ) : (
    <div className="w-full z-50">
      <Container className="z-50 space-y-8 pb-20 pt-6 md:pt-10">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:gap-6">
          <div className="relative h-28 w-20 shrink-0 overflow-hidden rounded-lg border border-slate-800/60 bg-slate-900/60 md:h-36 md:w-24">
            <Image
              src={anime.anime.info.poster}
              alt={anime.anime.info.name}
              height={144}
              width={96}
              className="h-full w-full object-cover"
              unoptimized
            />
          </div>
          <div className="flex flex-1 flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-extrabold md:text-4xl">
                {anime.anime.info.name}
              </h1>
              <span className="rounded-full bg-slate-800/70 px-2.5 py-1 text-xs font-semibold text-slate-100">
                ★ {anime.anime.info.stats.rating}
              </span>
              <span className="rounded-full border border-slate-700/70 px-2.5 py-1 text-xs uppercase tracking-wide text-slate-300">
                {anime.anime.info.stats.type}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant={isFavorite ? "secondary" : "default"}
                className="flex items-center gap-2"
                onClick={toggleFavorite}
                disabled={favoriteLoading || !canWriteContent}
              >
                <Heart
                  className="h-4 w-4"
                  fill={isFavorite ? "currentColor" : "none"}
                />
                {isFavorite ? "Remove from Favorites" : "Add to Favorites"}
              </Button>
            </div>
          </div>
        </div>
        <div className="space-y-6">
          {shouldRenderPlayer && (
            <PlayerShell layout="stacked" />
          )}
          {!episodesLoading && !hasEpisodes && (
            <div className="rounded-lg border border-slate-800/70 bg-slate-900/60 px-6 py-10 text-center text-sm text-slate-200">
              Episodes are not available yet.
            </div>
          )}
        </div>
        {hasRecommendations ? (
          <div className="space-y-6 border-t border-slate-800/70 pt-6">
            {!!anime.relatedAnimes.length && (
              <AnimeCarousel
                anime={anime.relatedAnimes as IAnime[]}
                title="Also Watch"
              />
            )}
            {!!anime.recommendedAnimes.length && (
              <AnimeCarousel
                anime={anime.recommendedAnimes as IAnime[]}
                title="Recommended"
              />
            )}
          </div>
        ) : null}
        <Tabs
          defaultValue="overview"
          className="w-full border-t border-slate-800/70 pt-6"
        >
          <TabsList className="flex h-fit w-full items-center justify-start gap-4">
            <TabsTrigger
              value="overview"
              className="text-base font-semibold md:text-lg"
            >
              Overview
            </TabsTrigger>
            {anime.anime.info.charactersVoiceActors.length > 0 && (
              <TabsTrigger
                value="characters"
                className="text-base font-semibold md:text-lg"
              >
                Characters
              </TabsTrigger>
            )}
            {anime.seasons.length > 0 && (
              <TabsTrigger
                value="relations"
                className="text-base font-semibold md:text-lg"
              >
                Relations
              </TabsTrigger>
            )}
          </TabsList>

          <TabsContent
            value="overview"
            className="mt-6 grid w-full grid-cols-1 gap-x-20 gap-y-6 md:grid-cols-5"
          >
            <div className="col-span-1 flex flex-col gap-5 w-full">
              <h3 className="text-lg font-semibold">Details</h3>
              <div className="grid w-full grid-cols-2 gap-x-10 gap-y-2 text-xs text-slate-300 md:text-sm">
                <h3 className="text-slate-400">Aired</h3>
                <span>{anime.anime.moreInfo.aired}</span>

                <h3 className="text-slate-400">Rating</h3>
                <span>{anime.anime.info.stats.rating}</span>

                <h3 className="text-slate-400">Genres</h3>
                <span>{anime.anime.moreInfo.genres.join(", ")}</span>

                <h3 className="text-slate-400">Type</h3>
                <span>{anime.anime.info.stats.type}</span>

                <h3 className="text-slate-400">Status</h3>
                <span>{anime.anime.moreInfo.status}</span>

                <h3 className="text-slate-400">Season</h3>
                <span className="capitalize">{}</span>

                <h3 className="text-slate-400">Studios</h3>
                <span>{anime.anime.moreInfo.studios}</span>
              </div>
            </div>
            <div className="col-span-4 flex flex-col gap-5">
              <h3 className="text-lg font-semibold">Description</h3>
              <p className="text-xs leading-6 text-slate-300 md:text-sm">
                {anime.anime.info.description}
              </p>
            </div>
          </TabsContent>

          <TabsContent
            value="relations"
            className="w-full flex flex-col gap-5 "
          >
            <h3 className="text-xl font-semibold">Relations</h3>
            <div className="grid lg:grid-cols-5 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-7 w-full gap-5 content-center">
              {anime.seasons.map((relation, idx) => {
                return (
                  !relation.isCurrent && (
                    <AnimeCard
                      key={idx}
                      title={relation.name}
                      subTitle={relation.title}
                      poster={relation.poster}
                      className="self-center justify-self-center"
                      href={`${ROUTES.ANIME_DETAILS}/${relation.id}`}
                    />
                  )
                );
              })}
            </div>
          </TabsContent>

          {!!anime.anime.info.charactersVoiceActors.length && (
            <TabsContent
              value="characters"
              className="w-full flex flex-col gap-5 "
            >
              <h3 className="text-xl font-semibold">Anime Characters</h3>
              <div className="grid lg:grid-cols-5 grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-7 w-full gap-5 content-center">
                {anime.anime.info.charactersVoiceActors.map(
                  (character, idx) => {
                    return (
                      <CharacterCard
                        key={idx}
                        character={character}
                        className="self-center justify-self-center"
                      />
                    );
                  },
                )}
              </div>
            </TabsContent>
          )}
        </Tabs>

      </Container>
    </div>
  );
  //eslint-disable-next-line
};

export default Page;
