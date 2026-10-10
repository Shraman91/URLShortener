"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useRouter } from "next/navigation";
import { Trash2, ExternalLink, BarChart3, Clock, Globe, Smartphone, Monitor, Plus, Zap, AlertCircle, ShieldCheck } from "lucide-react";
import Link from "next/link";

interface URLData {
  short_code: string;
  long_url: string;
  created_at: string;
  clicks: number;
  expires_at?: string;
  max_clicks?: number;
  is_password_protected: boolean;
  safety_score?: number;
  safety_verdict?: string;
  ai_category?: string;
  safety_flags?: string[];
}

interface URLStats {
  total_clicks: number;
  clicks_per_day: Record<string, number>;
  top_referrers: Record<string, number>;
  top_browsers: Record<string, number>;
  top_os?: Record<string, number>;
  top_devices: Record<string, number>;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DashboardPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  
  const [urls, setUrls] = useState<URLData[]>([]);
  const [fetchLoading, setFetchLoading] = useState(true);
  const [selectedStats, setSelectedStats] = useState<{code: string, stats: URLStats} | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (token) {
      fetchUrls();
    }
  }, [token]);

  const fetchUrls = async () => {
    try {
      const res = await fetch(`${API_URL}/api/my-urls`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUrls(data.urls);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setFetchLoading(false);
    }
  };

  const handleDelete = async (code: string) => {
    if (!confirm(`Are you sure you want to delete short link /${code}?`)) return;
    
    try {
      const res = await fetch(`${API_URL}/api/urls/${code}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setUrls(urls.filter(u => u.short_code !== code));
        if (selectedStats?.code === code) setSelectedStats(null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchStats = async (code: string) => {
    if (selectedStats?.code === code) {
      setSelectedStats(null);
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/stats/${code}/detailed`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedStats({ code, stats: data });
      } else {
        console.error("Failed to load stats:", res.status, await res.text());
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (loading || fetchLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="badge-brutal bg-brutal-yellow text-black animate-pulse text-sm">
          LOADING DASHBOARD...
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 bg-brutal-pink text-white badge-brutal mb-2 rotate-[-1deg]">
            <Zap className="w-3.5 h-3.5" />
            <span>Authenticated Creator Console</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-black text-black tracking-tight uppercase">
            My Dashboard
          </h1>
          <p className="text-sm sm:text-base font-bold text-gray-700 mt-1">
            Manage your personal links, inspect click trends, and analyze traffic.
          </p>
        </div>

        <Link
          href="/"
          className="btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-sm inline-flex items-center gap-2 self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>New Link</span>
        </Link>
      </div>

      {urls.length === 0 ? (
        <div className="card-brutal p-12 bg-white text-center">
          <h3 className="text-2xl font-black text-black uppercase mb-2">No Links Created Yet</h3>
          <p className="text-gray-600 font-bold text-sm mb-6">
            You haven't shortened any links with your account.
          </p>
          <button 
            onClick={() => router.push("/")}
            className="btn-brutal bg-brutal-yellow text-black text-sm"
          >
            Create Your First Link
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* URL List */}
          <div className="lg:col-span-2 space-y-4">
            {urls.map((url) => (
              <div 
                key={url.short_code} 
                className={`card-brutal p-5 bg-white transition-all ${
                  selectedStats?.code === url.short_code 
                    ? 'border-3 border-black bg-amber-50/40 shadow-brutal-lg' 
                    : 'hover:shadow-brutal-lg'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="space-y-2 overflow-hidden pr-4">
                    <a 
                      href={`http://localhost:8000/${url.short_code}`} 
                      target="_blank" 
                      rel="noreferrer" 
                      className="text-xl font-black text-black font-mono hover:text-brutal-pink flex items-center gap-2"
                    >
                      localhost:8000/{url.short_code}
                      <ExternalLink className="w-4 h-4 text-gray-400" />
                    </a>
                    
                    <p className="text-xs font-mono font-bold text-gray-700 truncate bg-brutal-paper border-2 border-black px-3 py-1.5 rounded-lg" title={url.long_url}>
                      {url.long_url}
                    </p>

                    <div className="flex flex-wrap gap-2 text-xs font-bold pt-1">
                      <span className="flex items-center gap-1 bg-brutal-paper border border-black px-2 py-0.5 rounded">
                        <Clock className="w-3 h-3" />
                        {new Date(url.created_at).toLocaleDateString()}
                      </span>

                      {/* AI Safety Score Badge */}
                      <span className={`flex items-center gap-1 border border-black px-2 py-0.5 rounded font-mono text-[11px] ${
                        (url.safety_score ?? 100) >= 85
                          ? "bg-emerald-200 text-emerald-950"
                          : (url.safety_score ?? 100) >= 65
                          ? "bg-amber-200 text-amber-950"
                          : "bg-red-200 text-red-950"
                      }`}>
                        <ShieldCheck className="w-3 h-3" />
                        AI: {url.safety_score ?? 100}/100 {url.safety_verdict || "SAFE"}
                      </span>

                      {url.ai_category && (
                        <span className="bg-purple-100 text-purple-950 border border-black px-2 py-0.5 rounded font-mono text-[11px]">
                          {url.ai_category}
                        </span>
                      )}

                      {url.is_password_protected && (
                        <span className="bg-brutal-pink text-white border border-black px-2 py-0.5 rounded">
                          Passcode Protected
                        </span>
                      )}
                      {url.expires_at && (
                        <span className="bg-red-100 text-red-900 border border-black px-2 py-0.5 rounded">
                          Expires: {new Date(url.expires_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  
                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button 
                      onClick={() => fetchStats(url.short_code)}
                      className={`btn-brutal text-xs py-1.5 px-3 flex items-center gap-1.5 ${
                        selectedStats?.code === url.short_code 
                          ? 'bg-black text-white' 
                          : 'bg-brutal-yellow text-black'
                      }`}
                    >
                      <BarChart3 className="w-3.5 h-3.5" />
                      <span>{url.clicks} Clicks</span>
                    </button>

                    <button 
                      onClick={() => handleDelete(url.short_code)}
                      className="p-2 border-2 border-black rounded-lg bg-white hover:bg-red-200 text-black shadow-brutal-sm transition-all"
                      title="Delete URL"
                    >
                      <Trash2 className="w-4 h-4 text-red-600" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Analytics Column */}
          <div className="lg:col-span-1">
            {selectedStats ? (
              <div className="card-brutal bg-white p-6 sticky top-24 shadow-brutal-lg animate-in fade-in slide-in-from-right-4">
                <div className="border-b-2 border-black pb-3 mb-5 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-black uppercase text-gray-500">Analytics</span>
                    <h3 className="text-xl font-black text-black font-mono">
                      /{selectedStats.code}
                    </h3>
                  </div>
                  <div className="badge-brutal bg-brutal-green text-black">
                    {selectedStats.stats.total_clicks} TOTAL
                  </div>
                </div>
                
                <div className="space-y-6">
                  {/* Referrers */}
                  <div>
                    <h4 className="text-xs font-black uppercase tracking-wider text-black mb-2 flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 text-brutal-blue" />
                      Top Referrers
                    </h4>
                    <div className="space-y-2">
                      {Object.entries(selectedStats.stats.top_referrers).map(([ref, count]) => (
                        <div key={ref} className="flex justify-between items-center text-xs font-bold border-2 border-black rounded-lg p-2 bg-brutal-paper">
                          <span className="truncate max-w-[170px]">{ref}</span>
                          <span className="bg-brutal-yellow border border-black px-2 py-0.5 rounded font-mono">{count}</span>
                        </div>
                      ))}
                      {Object.keys(selectedStats.stats.top_referrers).length === 0 && (
                        <p className="text-xs text-gray-500 italic font-medium">No referrer data yet</p>
                      )}
                    </div>
                  </div>

                  {/* Devices */}
                  <div>
                    <h4 className="text-xs font-black uppercase tracking-wider text-black mb-2 flex items-center gap-1.5">
                      <Smartphone className="w-3.5 h-3.5 text-brutal-green" />
                      Devices
                    </h4>
                    <div className="space-y-2">
                      {Object.entries(selectedStats.stats.top_devices).map(([dev, count]) => (
                        <div key={dev} className="flex justify-between items-center text-xs font-bold border-2 border-black rounded-lg p-2 bg-brutal-paper">
                          <span>{dev}</span>
                          <span className="bg-brutal-green border border-black px-2 py-0.5 rounded font-mono">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Operating Systems */}
                  {selectedStats.stats.top_os && Object.keys(selectedStats.stats.top_os).length > 0 && (
                    <div>
                      <h4 className="text-xs font-black uppercase tracking-wider text-black mb-2 flex items-center gap-1.5">
                        <Monitor className="w-3.5 h-3.5 text-brutal-yellow" />
                        Operating Systems
                      </h4>
                      <div className="space-y-2">
                        {Object.entries(selectedStats.stats.top_os).map(([osName, count]) => (
                          <div key={osName} className="flex justify-between items-center text-xs font-bold border-2 border-black rounded-lg p-2 bg-brutal-paper">
                            <span>{osName}</span>
                            <span className="bg-brutal-yellow border border-black px-2 py-0.5 rounded font-mono">{count}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Browsers */}
                  <div>
                    <h4 className="text-xs font-black uppercase tracking-wider text-black mb-2 flex items-center gap-1.5">
                      <Monitor className="w-3.5 h-3.5 text-brutal-purple" />
                      Browsers
                    </h4>
                    <div className="space-y-2">
                      {Object.entries(selectedStats.stats.top_browsers).map(([browser, count]) => (
                        <div key={browser} className="flex justify-between items-center text-xs font-bold border-2 border-black rounded-lg p-2 bg-brutal-paper">
                          <span>{browser}</span>
                          <span className="bg-brutal-pink text-white border border-black px-2 py-0.5 rounded font-mono">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="card-brutal p-8 bg-brutal-paper text-center flex flex-col items-center justify-center min-h-[300px]">
                <BarChart3 className="w-12 h-12 text-black mb-3 opacity-40" />
                <p className="text-black font-black uppercase text-xs tracking-wider">
                  Select a short link to inspect real-time click analytics
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
