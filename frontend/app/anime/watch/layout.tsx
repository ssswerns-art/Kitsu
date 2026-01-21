"use client";

import Loading from "@/app/loading";
import { ROUTES } from "@/constants/routes";

import Container from "@/components/container";
import AnimeCard from "@/components/anime-card";
import { useAnimeSelector } from "@/store/anime-store";

import { Heart } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useGetAnimeDetails } from "@/query/get-anime-details";
import React, { ReactNode, useEffect, useMemo, useState } from "react";
import AnimeCarousel from "@/components/anime-carousel";
import { IAnime } from "@/types/anime";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuthSelector } from "@/store/auth-store";
import { usePermissions } from "@/auth/rbac";

type Props = {
  children: ReactNode;
};

const Layout = (props: Props) => {
  const searchParams = useSearchParams();
  const setAnime = useAnimeSelector((state) => state.setAnime);
  const setSelectedEpisode = useAnimeSelector(
    (state) => state.setSelectedEpisode,
  );
  const router = useRouter();
  const auth = useAuthSelector((state) => state.auth);
  const permissions = usePermissions();
  const canWriteContent = permissions.includes("write:content");
  // RBAC NOTE:
  // write:content — visibility only (P1.4)
  // enforcement planned in P2

  const currentAnimeId = useMemo(
    () => searchParams.get("anime"),
    [searchParams],
  );
  const episodeId = searchParams.get("episode");

  const [animeId, setAnimeId] = useState<string | null>(currentAnimeId);

  useEffect(() => {
    if (currentAnimeId !== animeId) {
      setAnimeId(currentAnimeId);
    }

    if (episodeId) {
      setSelectedEpisode(episodeId);
    }
  }, [currentAnimeId, episodeId, animeId, setSelectedEpisode]);

  const { data: anime, isLoading } = useGetAnimeDetails(animeId as string);

  useEffect(() => {
    if (anime) {
      setAnime(anime);
    }
  }, [anime, setAnime]);

  useEffect(() => {
    if (!animeId) {
      router.push(ROUTES.HOME);
    }
    //eslint-disable-next-line
  }, [animeId, auth]);

  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteLoading, setFavoriteLoading] = useState(false);

  useEffect(() => {
    const loadFavorites = async () => {
      if (!animeId || !api) return;
      if (!auth) {
        setIsFavorite(false);
        return;
      }
      const res = await api.get("/favorites");
      const match = (res.data as any[])?.find(
        (fav) => fav.anime_id === animeId,
      );
      setIsFavorite(!!match);
    };
    loadFavorites();
  }, [animeId, auth]);

  const toggleFavorite = async () => {
    if (!animeId) return;
    if (!auth) {
      toast.error("Please login to manage favorites", {
        style: { background: "red" },
      });
      return;
    }
    setFavoriteLoading(true);
    if (isFavorite) {
      await api.delete(`/favorites/${animeId}`);
      setIsFavorite(false);
      toast.success("Removed from favorites", {
        style: { background: "green" },
      });
    } else {
      await api.post("/favorites", { anime_id: animeId });
      setIsFavorite(true);
      toast.success("Added to favorites", { style: { background: "green" } });
    }
    setFavoriteLoading(false);
  };

  if (isLoading) return <Loading />;

  return (
    anime?.anime.info && (
      <Container className="mt-[6.5rem] space-y-10 pb-20">
        {props.children}
        <div className="flex md:flex-row flex-col gap-5 -mt-5">
          <AnimeCard
            title={anime?.anime.info.name}
            poster={anime?.anime.info.poster}
            subTitle={anime?.anime.moreInfo.aired}
            displayDetails={false}
            className="!h-full !rounded-sm"
            href={ROUTES.ANIME_DETAILS + "/" + anime?.anime.info.id}
          />
          <div className="flex flex-col gap-2">
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
            <h1 className="text-2xl md:font-black font-extrabold z-[100]">
              {anime?.anime.info.name}
            </h1>
            <p>{anime?.anime.info.description}</p>
          </div>
        </div>
        <AnimeCarousel
          title={"Also Watch"}
          anime={anime?.relatedAnimes as IAnime[]}
        />
        <AnimeCarousel
          title={"Recommended"}
          anime={anime?.recommendedAnimes as IAnime[]}
        />
      </Container>
    )
  );
};
export default Layout;
