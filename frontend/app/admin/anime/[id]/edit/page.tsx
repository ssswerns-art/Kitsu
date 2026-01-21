"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";
import { useAuthSelector, useAuthHydrated } from "@/store/auth-store";
import { usePermissions } from "@/auth/rbac";
import Loading from "@/app/loading";

interface AnimeDetail {
  id: string;
  title: string;
  title_ru: string | null;
  title_en: string | null;
  title_original: string | null;
  description: string | null;
  poster_url: string | null;
  year: number | null;
  season: string | null;
  status: string | null;
  genres: string[] | null;
  state: string;
  source: string;
  is_locked: boolean;
  locked_fields: string[] | null;
  locked_reason: string | null;
  has_video: boolean;
  errors_count: number;
  errors: string[];
}

const STATE_TRANSITIONS = {
  draft: ["pending", "broken", "archived"],
  pending: ["published", "draft", "broken", "archived"],
  published: ["archived", "broken"],
  broken: ["draft", "pending", "archived"],
  archived: ["draft"],
};

export default function EditAnimePage() {
  const router = useRouter();
  const params = useParams();
  const animeId = params.id as string;
  
  const auth = useAuthSelector((state) => state.auth);
  const hasHydrated = useAuthHydrated();
  const permissions = usePermissions();
  
  const [anime, setAnime] = useState<AnimeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Form fields
  const [title, setTitle] = useState("");
  const [titleRu, setTitleRu] = useState("");
  const [titleEn, setTitleEn] = useState("");
  const [description, setDescription] = useState("");
  const [state, setState] = useState("");
  const [reason, setReason] = useState("");
  
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
        const response = await fetch(`/api/admin/anime/${animeId}`, {
          headers: {
            Authorization: `Bearer ${auth.accessToken}`,
          },
        });

        if (!response.ok) {
          throw new Error("Failed to fetch anime");
        }

        const data = await response.json();
        setAnime(data);
        setTitle(data.title || "");
        setTitleRu(data.title_ru || "");
        setTitleEn(data.title_en || "");
        setDescription(data.description || "");
        setState(data.state || "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchAnime();
  }, [hasHydrated, auth, canView, animeId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!auth || !canEdit) return;

    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      const update: any = {};
      if (title !== anime?.title) update.title = title;
      if (titleRu !== anime?.title_ru) update.title_ru = titleRu || null;
      if (titleEn !== anime?.title_en) update.title_en = titleEn || null;
      if (description !== anime?.description) update.description = description || null;
      if (state !== anime?.state) update.state = state;
      if (reason) update.reason = reason;

      const response = await fetch(`/api/admin/anime/${animeId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${auth.accessToken}`,
        },
        body: JSON.stringify(update),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to update anime");
      }

      const result = await response.json();
      setSuccess("Anime updated successfully!");
      
      // Update local state
      setAnime(result.anime);
      
      // Show warnings if any
      if (result.warnings && result.warnings.length > 0) {
        setError(`Warnings: ${result.warnings.join(", ")}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  };

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
          <p className="text-red-700">You do not have permission to view anime.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return <Loading />;
  }

  if (!anime) {
    return (
      <div className="container mx-auto p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h2 className="text-xl font-bold text-red-900">Not Found</h2>
          <p className="text-red-700">Anime not found.</p>
        </div>
      </div>
    );
  }

  const isFieldLocked = (field: string) => {
    return anime.is_locked && anime.locked_fields?.includes(field);
  };

  const allowedTransitions = STATE_TRANSITIONS[anime.state as keyof typeof STATE_TRANSITIONS] || [];

  return (
    <div className="container mx-auto p-8 max-w-4xl">
      <div className="mb-6">
        <button
          onClick={() => router.back()}
          className="text-blue-600 hover:text-blue-800 mb-4"
        >
          ← Back to List
        </button>
        <h1 className="text-3xl font-bold mb-2">Edit Anime</h1>
        <p className="text-gray-600">ID: {anime.id}</p>
      </div>

      {/* Status indicators */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white border rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">State</div>
          <div className="font-semibold">{anime.state}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Source</div>
          <div className="font-semibold">{anime.source}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="text-sm text-gray-600 mb-1">Has Video</div>
          <div className="font-semibold">{anime.has_video ? "Yes ✓" : "No ✗"}</div>
        </div>
      </div>

      {/* Errors */}
      {anime.errors_count > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <h3 className="font-semibold text-red-900 mb-2">Errors ({anime.errors_count})</h3>
          <ul className="list-disc list-inside text-red-700">
            {anime.errors.map((err, idx) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Lock status */}
      {anime.is_locked && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
          <h3 className="font-semibold text-yellow-900 mb-2">🔒 Locked</h3>
          {anime.locked_reason && (
            <p className="text-yellow-700 mb-2">Reason: {anime.locked_reason}</p>
          )}
          {anime.locked_fields && anime.locked_fields.length > 0 && (
            <p className="text-yellow-700">
              Locked fields: {anime.locked_fields.join(", ")}
            </p>
          )}
        </div>
      )}

      {/* Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
          <p className="text-green-700">{success}</p>
        </div>
      )}

      {/* Edit form */}
      {canEdit ? (
        <form onSubmit={handleSubmit} className="bg-white border rounded-lg p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Title {isFieldLocked("title") && "🔒"}
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={isFieldLocked("title")}
                className="w-full border rounded px-3 py-2 disabled:bg-gray-100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Title (Russian) {isFieldLocked("title_ru") && "🔒"}
              </label>
              <input
                type="text"
                value={titleRu}
                onChange={(e) => setTitleRu(e.target.value)}
                disabled={isFieldLocked("title_ru")}
                className="w-full border rounded px-3 py-2 disabled:bg-gray-100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Title (English) {isFieldLocked("title_en") && "🔒"}
              </label>
              <input
                type="text"
                value={titleEn}
                onChange={(e) => setTitleEn(e.target.value)}
                disabled={isFieldLocked("title_en")}
                className="w-full border rounded px-3 py-2 disabled:bg-gray-100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Description {isFieldLocked("description") && "🔒"}
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isFieldLocked("description")}
                rows={6}
                className="w-full border rounded px-3 py-2 disabled:bg-gray-100"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">State</label>
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full border rounded px-3 py-2"
              >
                <option value={anime.state}>{anime.state} (current)</option>
                {allowedTransitions.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              {allowedTransitions.length > 0 && (
                <p className="text-sm text-gray-600 mt-1">
                  Allowed transitions: {allowedTransitions.join(", ")}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Update Reason (for audit log)
              </label>
              <input
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full border rounded px-3 py-2"
                placeholder="e.g., Fixed title typo"
              />
            </div>

            <div className="flex gap-4">
              <button
                type="submit"
                disabled={saving}
                className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
              <button
                type="button"
                onClick={() => router.back()}
                className="px-6 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      ) : (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-yellow-700">
            You do not have permission to edit anime. View-only mode.
          </p>
        </div>
      )}
    </div>
  );
}
