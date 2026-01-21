"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthSelector, useAuthHydrated } from "@/store/auth-store";
import { usePermissions } from "@/auth/rbac";
import Loading from "@/app/loading";

interface AnimeListItem {
  id: string;
  title: string;
  poster_url: string | null;
  state: string;
  source: string;
  year: number | null;
  status: string | null;
  is_locked: boolean;
  locked_fields: string[] | null;
  has_video: boolean;
  errors_count: number;
  created_at: string;
  updated_at: string;
}

interface AnimeListResponse {
  items: AnimeListItem[];
  total: number;
  limit: number;
  offset: number;
}

export default function AdminAnimePage() {
  const router = useRouter();
  const auth = useAuthSelector((state) => state.auth);
  const hasHydrated = useAuthHydrated();
  const permissions = usePermissions();
  
  const [animeList, setAnimeList] = useState<AnimeListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Filters
  const [state, setState] = useState<string>("");
  const [source, setSource] = useState<string>("");
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortOrder, setSortOrder] = useState("desc");
  
  // Check permissions
  const canView = permissions.includes("anime.view");
  const canEdit = permissions.includes("anime.edit");

  useEffect(() => {
    if (hasHydrated && !auth) {
      router.replace("/");
    }
  }, [auth, hasHydrated, router]);

  useEffect(() => {
    if (!hasHydrated || !auth || !canView) return;

    const fetchAnime = async () => {
      try {
        setLoading(true);
        const params = new URLSearchParams({
          limit: "30",
          offset: "0",
          sort_by: sortBy,
          sort_order: sortOrder,
        });
        
        if (state) params.append("state", state);
        if (source) params.append("source", source);

        const response = await fetch(`/api/admin/anime?${params}`, {
          headers: {
            Authorization: `Bearer ${auth.accessToken}`,
          },
        });

        if (!response.ok) {
          throw new Error("Failed to fetch anime");
        }

        const data = await response.json();
        setAnimeList(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchAnime();
  }, [hasHydrated, auth, canView, state, source, sortBy, sortOrder]);

  if (!hasHydrated) {
    return <Loading />;
  }

  if (!auth) {
    return null;
  }

  if (!canView) {
    return (
      <div className="container mx-auto p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h2 className="text-xl font-bold text-red-900">Permission Denied</h2>
          <p className="text-red-700">You do not have permission to view anime management.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Anime Management</h1>
        <p className="text-gray-600">Manage anime content with CMS-level controls</p>
      </div>

      {/* Filters */}
      <div className="bg-white border rounded-lg p-4 mb-6">
        <h2 className="text-lg font-semibold mb-4">Filters</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">State</label>
            <select
              value={state}
              onChange={(e) => setState(e.target.value)}
              className="w-full border rounded px-3 py-2"
            >
              <option value="">All</option>
              <option value="draft">Draft</option>
              <option value="pending">Pending</option>
              <option value="published">Published</option>
              <option value="broken">Broken</option>
              <option value="archived">Archived</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Source</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full border rounded px-3 py-2"
            >
              <option value="">All</option>
              <option value="manual">Manual</option>
              <option value="parser">Parser</option>
              <option value="import">Import</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Sort By</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full border rounded px-3 py-2"
            >
              <option value="updated_at">Updated Date</option>
              <option value="created_at">Created Date</option>
              <option value="title">Title</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Sort Order</label>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              className="w-full border rounded px-3 py-2"
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </div>
        </div>
      </div>

      {/* Anime List */}
      {loading && <div className="text-center py-8">Loading...</div>}
      
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-700">Error: {error}</p>
        </div>
      )}

      {animeList && (
        <div className="bg-white border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-semibold">Title</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold">State</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold">Source</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold">Video</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold">Errors</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold">Locked</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {animeList.items.map((anime) => (
                  <tr key={anime.id} className={anime.state === "broken" ? "bg-red-50" : ""}>
                    <td className="px-4 py-3">{anime.title}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        anime.state === "published" ? "bg-green-100 text-green-800" :
                        anime.state === "broken" ? "bg-red-100 text-red-800" :
                        anime.state === "draft" ? "bg-gray-100 text-gray-800" :
                        anime.state === "pending" ? "bg-yellow-100 text-yellow-800" :
                        "bg-gray-100 text-gray-800"
                      }`}>
                        {anime.state}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">{anime.source}</td>
                    <td className="px-4 py-3">
                      {anime.has_video ? (
                        <span className="text-green-600">✓</span>
                      ) : (
                        <span className="text-red-600">✗</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {anime.errors_count > 0 && (
                        <span className="text-red-600 font-medium">{anime.errors_count}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {anime.is_locked && (
                        <span className="text-yellow-600">🔒</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {canEdit && (
                        <button
                          onClick={() => router.push(`/admin/anime/${anime.id}/edit`)}
                          className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                        >
                          Edit
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <div className="px-4 py-3 bg-gray-50 border-t">
            <p className="text-sm text-gray-600">
              Showing {animeList.items.length} of {animeList.total} anime
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
