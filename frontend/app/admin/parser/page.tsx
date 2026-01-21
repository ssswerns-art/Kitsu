"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthSelector, useAuthHydrated } from "@/store/auth-store";
import { usePermissions } from "@/auth/rbac";
import Loading from "@/app/loading";

interface ParserSource {
  id: number;
  code: string;
  enabled: boolean;
}

interface ParserDashboard {
  sources: ParserSource[];
  anime_external_count: number;
  unmapped_anime_count: number;
  episodes_external_count: number;
  jobs_last_24h: number;
  errors_count: number;
}

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

export default function ParserDashboardPage() {
  const router = useRouter();
  const auth = useAuthSelector((state) => state.auth);
  const hasHydrated = useAuthHydrated();
  const permissions = usePermissions();
  
  const [dashboard, setDashboard] = useState<ParserDashboard | null>(null);
  const [settings, setSettings] = useState<ParserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  
  // Check permissions
  const canViewLogs = permissions.includes("admin:parser.logs");
  const canManageSettings = permissions.includes("admin:parser.settings");
  const canEmergencyStop = permissions.includes("admin:parser.emergency");

  useEffect(() => {
    if (hasHydrated && !auth) {
      router.replace("/");
    }
  }, [auth, hasHydrated, router]);

  useEffect(() => {
    if (!hasHydrated || !auth || !canViewLogs) return;

    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch dashboard data
        const dashboardResponse = await fetch("/api/admin/parser/dashboard", {
          headers: {
            Authorization: `Bearer ${auth.accessToken}`,
          },
        });

        if (!dashboardResponse.ok) {
          throw new Error("Failed to fetch dashboard");
        }

        const dashboardData = await dashboardResponse.json();
        setDashboard(dashboardData);
        
        // Fetch settings
        if (canManageSettings) {
          const settingsResponse = await fetch("/api/admin/parser/settings", {
            headers: {
              Authorization: `Bearer ${auth.accessToken}`,
            },
          });

          if (settingsResponse.ok) {
            const settingsData = await settingsResponse.json();
            setSettings(settingsData);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [hasHydrated, auth, canViewLogs, canManageSettings]);

  const handleModeToggle = async (newMode: "manual" | "auto") => {
    if (!auth || !canManageSettings) return;
    
    const confirmMessage = newMode === "auto"
      ? "Enable automatic parser mode? Parser will run automatically based on schedule."
      : "Disable automatic parser mode? Parser will only run manually.";
    
    if (!confirm(confirmMessage)) return;
    
    const reason = prompt("Reason for mode change (optional):");
    
    try {
      setActionLoading(true);
      const response = await fetch("/api/admin/parser/mode", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${auth.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ mode: newMode, reason }),
      });

      if (!response.ok) {
        throw new Error("Failed to toggle mode");
      }

      // Refresh settings
      const settingsResponse = await fetch("/api/admin/parser/settings", {
        headers: {
          Authorization: `Bearer ${auth.accessToken}`,
        },
      });

      if (settingsResponse.ok) {
        const settingsData = await settingsResponse.json();
        setSettings(settingsData);
      }
      
      alert(`Parser mode changed to ${newMode}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to toggle mode");
    } finally {
      setActionLoading(false);
    }
  };

  const handleEmergencyStop = async () => {
    if (!auth || !canEmergencyStop) return;
    
    const reason = prompt("EMERGENCY STOP - Please provide a reason:");
    if (!reason) return;
    
    if (!confirm("Are you sure you want to EMERGENCY STOP the parser? This will stop all running jobs.")) {
      return;
    }
    
    try {
      setActionLoading(true);
      const response = await fetch("/api/admin/parser/emergency-stop", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${auth.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason }),
      });

      if (!response.ok) {
        throw new Error("Failed to emergency stop");
      }

      // Refresh settings
      const settingsResponse = await fetch("/api/admin/parser/settings", {
        headers: {
          Authorization: `Bearer ${auth.accessToken}`,
        },
      });

      if (settingsResponse.ok) {
        const settingsData = await settingsResponse.json();
        setSettings(settingsData);
      }
      
      alert("Emergency stop executed successfully");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to emergency stop");
    } finally {
      setActionLoading(false);
    }
  };

  if (!hasHydrated) {
    return <Loading />;
  }

  if (!auth) {
    return null;
  }

  if (!canViewLogs) {
    return (
      <div className="container mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">Access Denied</h1>
        <p>You don&apos;t have permission to view the parser dashboard.</p>
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
        <h1 className="text-3xl font-bold">Parser Dashboard</h1>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/admin/parser/settings")}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            disabled={!canManageSettings}
          >
            Settings
          </button>
          <button
            onClick={() => router.push("/admin/parser/logs")}
            className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            Logs
          </button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Mode</h3>
          <div className="mt-2 flex items-center gap-2">
            <span className={`inline-flex px-3 py-1 text-sm font-semibold rounded-full ${
              settings?.mode === "auto" 
                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300" 
                : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
            }`}>
              {settings?.mode === "auto" ? "Auto" : "Manual"}
            </span>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Dry Run</h3>
          <div className="mt-2">
            <span className={`inline-flex px-3 py-1 text-sm font-semibold rounded-full ${
              settings?.dry_run_default 
                ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300" 
                : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
            }`}>
              {settings?.dry_run_default ? "ON" : "OFF"}
            </span>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Errors (24h)</h3>
          <div className="mt-2">
            <span className={`text-2xl font-bold ${
              (dashboard?.errors_count ?? 0) > 0 ? "text-red-600" : "text-green-600"
            }`}>
              {dashboard?.errors_count ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">External Anime</h3>
          <p className="mt-2 text-2xl font-bold">{dashboard?.anime_external_count ?? 0}</p>
        </div>

        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Unmapped</h3>
          <p className="mt-2 text-2xl font-bold text-orange-600">{dashboard?.unmapped_anime_count ?? 0}</p>
        </div>

        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Episodes</h3>
          <p className="mt-2 text-2xl font-bold">{dashboard?.episodes_external_count ?? 0}</p>
        </div>

        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Jobs (24h)</h3>
          <p className="mt-2 text-2xl font-bold">{dashboard?.jobs_last_24h ?? 0}</p>
        </div>
      </div>

      {/* Sources */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow mb-6">
        <h2 className="text-xl font-bold mb-4">Enabled Sources</h2>
        <div className="flex flex-wrap gap-2">
          {dashboard?.sources.map((source) => (
            <span
              key={source.id}
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                source.enabled
                  ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                  : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
              }`}
            >
              {source.code}
            </span>
          ))}
        </div>
      </div>

      {/* Actions */}
      {canManageSettings && (
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
          <h2 className="text-xl font-bold mb-4">Actions</h2>
          <div className="flex flex-wrap gap-2">
            {settings?.mode === "manual" ? (
              <button
                onClick={() => handleModeToggle("auto")}
                disabled={actionLoading}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
              >
                Enable Auto Mode
              </button>
            ) : (
              <button
                onClick={() => handleModeToggle("manual")}
                disabled={actionLoading}
                className="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 disabled:opacity-50"
              >
                Disable Auto Mode
              </button>
            )}
            
            {canEmergencyStop && (
              <button
                onClick={handleEmergencyStop}
                disabled={actionLoading}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
              >
                Emergency Stop
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
