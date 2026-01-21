"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthSelector, useAuthHydrated } from "@/store/auth-store";
import { usePermissions } from "@/auth/rbac";
import Loading from "@/app/loading";

interface ParserSettings {
  mode: "manual" | "auto";
  stage_only: boolean;
  autopublish_enabled: boolean;
  enable_autoupdate: boolean;
  update_interval_minutes: number;
  dry_run_default: boolean;
  allowed_translation_types: string[];
  allowed_translations: string[];
  allowed_qualities: string[];
  preferred_translation_priority: string[];
  preferred_quality_priority: string[];
  blacklist_titles: string[];
  blacklist_external_ids: string[];
}

export default function ParserSettingsPage() {
  const router = useRouter();
  const auth = useAuthSelector((state) => state.auth);
  const hasHydrated = useAuthHydrated();
  const permissions = usePermissions();
  
  const [settings, setSettings] = useState<ParserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [formData, setFormData] = useState<Partial<ParserSettings>>({});
  
  // Check permissions
  const canManageSettings = permissions.includes("admin:parser.settings");

  useEffect(() => {
    if (hasHydrated && !auth) {
      router.replace("/");
    }
  }, [auth, hasHydrated, router]);

  useEffect(() => {
    if (!hasHydrated || !auth || !canManageSettings) return;

    const fetchSettings = async () => {
      try {
        setLoading(true);
        const response = await fetch("/api/admin/parser/settings", {
          headers: {
            Authorization: `Bearer ${auth.accessToken}`,
          },
        });

        if (!response.ok) {
          throw new Error("Failed to fetch settings");
        }

        const data = await response.json();
        setSettings(data);
        setFormData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, [hasHydrated, auth, canManageSettings]);

  const handleSave = async () => {
    if (!auth || !canManageSettings) return;
    
    if (!confirm("Save parser settings? This will affect parser behavior.")) {
      return;
    }
    
    try {
      setSaving(true);
      const response = await fetch("/api/admin/parser/settings", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${auth.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error("Failed to save settings");
      }

      const data = await response.json();
      setSettings(data);
      setFormData(data);
      
      alert("Settings saved successfully");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (settings) {
      setFormData(settings);
    }
  };

  if (!hasHydrated) {
    return <Loading />;
  }

  if (!auth) {
    return null;
  }

  if (!canManageSettings) {
    return (
      <div className="container mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">Access Denied</h1>
        <p>You don&apos;t have permission to manage parser settings.</p>
      </div>
    );
  }

  if (loading) {
    return <Loading />;
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">Error</h1>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Parser Settings</h1>
        <button
          onClick={() => router.push("/admin/parser")}
          className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
        >
          Back to Dashboard
        </button>
      </div>

      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow space-y-6">
        {/* Mode */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Mode
            <span className="ml-2 text-xs text-gray-500">(Changed via dashboard mode toggle)</span>
          </label>
          <div className="flex items-center gap-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              formData.mode === "auto" 
                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300" 
                : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
            }`}>
              {formData.mode === "auto" ? "Auto" : "Manual"}
            </span>
          </div>
        </div>

        {/* Dry Run */}
        <div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={formData.dry_run_default ?? false}
              onChange={(e) => setFormData({ ...formData, dry_run_default: e.target.checked })}
              className="w-4 h-4"
            />
            <span className="text-sm font-medium">Dry Run (Default)</span>
          </label>
          <p className="text-xs text-gray-500 mt-1">
            When enabled, parser will simulate actions without persisting changes
          </p>
        </div>

        {/* Auto-update */}
        <div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={formData.enable_autoupdate ?? false}
              onChange={(e) => setFormData({ ...formData, enable_autoupdate: e.target.checked })}
              className="w-4 h-4"
            />
            <span className="text-sm font-medium">Enable Auto-update</span>
          </label>
          <p className="text-xs text-gray-500 mt-1">
            Automatically check for new episodes from external sources
          </p>
        </div>

        {/* Update Interval */}
        {formData.enable_autoupdate && (
          <div>
            <label className="block text-sm font-medium mb-2">
              Update Interval (minutes)
            </label>
            <input
              type="number"
              min="1"
              max="1440"
              value={formData.update_interval_minutes ?? 60}
              onChange={(e) => setFormData({ ...formData, update_interval_minutes: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
            />
          </div>
        )}

        {/* Translation Types */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Allowed Translation Types
          </label>
          <div className="space-y-2">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.allowed_translation_types?.includes("voice") ?? false}
                onChange={(e) => {
                  const types = formData.allowed_translation_types || [];
                  if (e.target.checked) {
                    setFormData({ ...formData, allowed_translation_types: [...types, "voice"] });
                  } else {
                    setFormData({ ...formData, allowed_translation_types: types.filter(t => t !== "voice") });
                  }
                }}
                className="w-4 h-4"
              />
              <span className="text-sm">Voice (Dubbed)</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.allowed_translation_types?.includes("sub") ?? false}
                onChange={(e) => {
                  const types = formData.allowed_translation_types || [];
                  if (e.target.checked) {
                    setFormData({ ...formData, allowed_translation_types: [...types, "sub"] });
                  } else {
                    setFormData({ ...formData, allowed_translation_types: types.filter(t => t !== "sub") });
                  }
                }}
                className="w-4 h-4"
              />
              <span className="text-sm">Subtitles</span>
            </label>
          </div>
        </div>

        {/* Allowed Translations */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Allowed Translations (comma-separated)
          </label>
          <input
            type="text"
            value={formData.allowed_translations?.join(", ") ?? ""}
            onChange={(e) => setFormData({ 
              ...formData, 
              allowed_translations: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
            })}
            placeholder="AniLibria, AniDub, etc."
            className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
          />
        </div>

        {/* Allowed Qualities */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Allowed Qualities (comma-separated)
          </label>
          <input
            type="text"
            value={formData.allowed_qualities?.join(", ") ?? ""}
            onChange={(e) => setFormData({ 
              ...formData, 
              allowed_qualities: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
            })}
            placeholder="1080p, 720p, 480p"
            className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
          />
        </div>

        {/* Translation Priority */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Translation Priority (comma-separated, highest first)
          </label>
          <input
            type="text"
            value={formData.preferred_translation_priority?.join(", ") ?? ""}
            onChange={(e) => setFormData({ 
              ...formData, 
              preferred_translation_priority: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
            })}
            placeholder="AniLibria, AniDub"
            className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
          />
        </div>

        {/* Quality Priority */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Quality Priority (comma-separated, highest first)
          </label>
          <input
            type="text"
            value={formData.preferred_quality_priority?.join(", ") ?? ""}
            onChange={(e) => setFormData({ 
              ...formData, 
              preferred_quality_priority: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
            })}
            placeholder="1080p, 720p"
            className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
          />
        </div>

        {/* Blacklist Titles */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Blacklist Titles (comma-separated)
          </label>
          <input
            type="text"
            value={formData.blacklist_titles?.join(", ") ?? ""}
            onChange={(e) => setFormData({ 
              ...formData, 
              blacklist_titles: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
            })}
            placeholder="Blocked Title 1, Blocked Title 2"
            className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
          />
        </div>

        {/* Blacklist External IDs */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Blacklist External IDs (comma-separated)
          </label>
          <input
            type="text"
            value={formData.blacklist_external_ids?.join(", ") ?? ""}
            onChange={(e) => setFormData({ 
              ...formData, 
              blacklist_external_ids: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
            })}
            placeholder="12345, 67890"
            className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600"
          />
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 pt-4 border-t dark:border-gray-700">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
          <button
            onClick={handleReset}
            disabled={saving}
            className="px-6 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 disabled:opacity-50"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
