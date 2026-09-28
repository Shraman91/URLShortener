"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useRouter } from "next/navigation";
import { Trash2, ExternalLink, BarChart3, Clock, Globe, Smartphone, Monitor } from "lucide-react";

interface URLData {
  short_code: string;
  long_url: string;
  created_at: string;
  clicks: number;
  expires_at?: string;
  max_clicks?: number;
  is_password_protected: boolean;
}

interface URLStats {
  total_clicks: number;
  clicks_per_day: Record<string, number>;
  top_referrers: Record<string, number>;
  top_browsers: Record<string, number>;
  top_devices: Record<string, number>;
}

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
      const res = await fetch("http://localhost:8000/api/my-urls", {
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
    if (!confirm("Are you sure you want to delete this URL?")) return;
    
    try {
      const res = await fetch(`http://localhost:8000/api/urls/${code}`, {
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
      const res = await fetch(`http://localhost:8000/api/stats/${code}/detailed`);
      if (res.ok) {
        const data = await res.json();
        setSelectedStats({ code, stats: data });
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (loading || fetchLoading) {
    return <div className="flex justify-center items-center h-64 text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="max-w-6xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Manage your shortened URLs and view analytics.</p>
        </div>
      </div>

      {urls.length === 0 ? (
        <div className="bg-white p-10 rounded-2xl border border-border text-center shadow-sm">
          <h3 className="text-xl font-semibold text-foreground mb-2">No URLs found</h3>
          <p className="text-muted-foreground mb-6">You haven't shortened any URLs yet.</p>
          <button 
            onClick={() => router.push("/")}
            className="bg-primary text-primary-foreground px-6 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity"
          >
            Create your first link
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {urls.map((url) => (
              <div key={url.short_code} className={`bg-white rounded-xl border p-5 transition-all ${selectedStats?.code === url.short_code ? 'border-primary shadow-md' : 'border-border shadow-sm hover:border-gray-300'}`}>
                <div className="flex justify-between items-start">
                  <div className="space-y-1 overflow-hidden pr-4">
                    <a href={`http://localhost:8000/${url.short_code}`} target="_blank" rel="noreferrer" className="text-lg font-bold text-primary hover:underline flex items-center gap-2">
                      localhost:8000/{url.short_code}
                      <ExternalLink className="w-4 h-4 text-muted-foreground" />
                    </a>
                    <p className="text-sm text-muted-foreground truncate" title={url.long_url}>
                      {url.long_url}
                    </p>
                    <div className="flex gap-4 mt-2 text-xs text-muted-foreground font-medium">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(url.created_at).toLocaleDateString()}
                      </span>
                      {url.is_password_protected && (
                        <span className="bg-muted px-2 py-0.5 rounded text-primary">Password Protected</span>
                      )}
                      {url.expires_at && (
                        <span className="bg-red-50 text-red-700 px-2 py-0.5 rounded">
                          Expires: {new Date(url.expires_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button 
                      onClick={() => fetchStats(url.short_code)}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${selectedStats?.code === url.short_code ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground hover:bg-gray-200'}`}
                    >
                      <BarChart3 className="w-4 h-4" />
                      {url.clicks} Clicks
                    </button>
                    <button 
                      onClick={() => handleDelete(url.short_code)}
                      className="p-1.5 text-muted-foreground hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete URL"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="lg:col-span-1">
            {selectedStats ? (
              <div className="bg-white rounded-xl border border-border p-6 shadow-sm sticky top-6 animate-in fade-in slide-in-from-right-4">
                <h3 className="text-xl font-bold text-foreground border-b border-border pb-4 mb-4">
                  Analytics for /{selectedStats.code}
                </h3>
                
                <div className="space-y-6">
                  <div>
                    <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">Top Referrers</h4>
                    <div className="space-y-2">
                      {Object.entries(selectedStats.stats.top_referrers).map(([ref, count]) => (
                        <div key={ref} className="flex justify-between items-center text-sm">
                          <span className="flex items-center gap-2 truncate max-w-[200px]">
                            <Globe className="w-4 h-4 text-muted-foreground" />
                            {ref}
                          </span>
                          <span className="font-medium bg-muted px-2 py-0.5 rounded">{count}</span>
                        </div>
                      ))}
                      {Object.keys(selectedStats.stats.top_referrers).length === 0 && (
                        <p className="text-sm text-muted-foreground italic">No data yet</p>
                      )}
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">Top Devices</h4>
                    <div className="space-y-2">
                      {Object.entries(selectedStats.stats.top_devices).map(([dev, count]) => (
                        <div key={dev} className="flex justify-between items-center text-sm">
                          <span className="flex items-center gap-2">
                            {dev.toLowerCase().includes('mac') || dev.toLowerCase().includes('windows') ? 
                              <Monitor className="w-4 h-4 text-muted-foreground" /> : 
                              <Smartphone className="w-4 h-4 text-muted-foreground" />}
                            {dev}
                          </span>
                          <span className="font-medium bg-muted px-2 py-0.5 rounded">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                   <div>
                    <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">Top Browsers</h4>
                    <div className="space-y-2">
                      {Object.entries(selectedStats.stats.top_browsers).map(([browser, count]) => (
                        <div key={browser} className="flex justify-between items-center text-sm">
                          <span className="truncate">{browser}</span>
                          <span className="font-medium bg-muted px-2 py-0.5 rounded">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-muted/50 rounded-xl border border-dashed border-border p-10 text-center flex flex-col items-center justify-center h-full min-h-[300px]">
                <BarChart3 className="w-12 h-12 text-muted-foreground mb-4 opacity-50" />
                <p className="text-muted-foreground font-medium">Select a URL to view detailed analytics</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
