"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  Activity, 
  Zap, 
  Database, 
  Layers, 
  ShieldAlert, 
  Clock, 
  TrendingUp, 
  RefreshCw, 
  CheckCircle2, 
  Server, 
  Cpu, 
  Gauge, 
  Flame, 
  Lock, 
  Globe, 
  AlertOctagon,
  ArrowUpRight,
  HardDrive
} from "lucide-react";

interface ObservabilityData {
  status: string;
  uptime_seconds: number;
  timestamp: string;
  cache: {
    backend: string;
    is_redis_active: boolean;
    hits: number;
    misses: number;
    negative_hits: number;
    total_lookups: number;
    hit_rate_pct: number;
    items_in_l1: number;
    negative_items: number;
  };
  queue: {
    queue_size: number;
    total_enqueued: number;
    total_flushed: number;
    total_batches: number;
    last_flush_time: string | null;
    is_worker_running: boolean;
  };
  latency: {
    total_requests: number;
    avg_latency_ms: number;
    p50_latency_ms: number;
    p95_latency_ms: number;
    p99_latency_ms: number;
    min_latency_ms: number;
    max_latency_ms: number;
    requests_per_minute: number;
    status_codes: Record<string, number>;
  };
  rate_limiter: {
    backend: string;
    total_checks: number;
    total_blocked: number;
    block_rate_pct: number;
    blocks_by_scope: Record<string, number>;
    recent_blocked_events: Array<{
      timestamp: string;
      scope: string;
      tier: string;
      client: string;
    }>;
  };
}

export default function ObservabilityDashboard() {
  const [data, setData] = useState<ObservabilityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);

  const fetchTelemetry = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/observability", {
        cache: "no-store",
      });
      if (!res.ok) throw new Error("Failed to reach observability gateway");
      const result = await res.json();
      setData(result);
      setLastRefreshed(new Date());
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Backend offline");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    if (!autoRefresh) return;
    const interval = setInterval(fetchTelemetry, 2500);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const formatUptime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const hrs = Math.floor(mins / 60);
    if (hrs > 0) return `${hrs}h ${mins % 60}m`;
    if (mins > 0) return `${mins}m ${Math.floor(seconds % 60)}s`;
    return `${Math.floor(seconds)}s`;
  };

  return (
    <div className="max-w-6xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 bg-brutal-green text-black badge-brutal mb-3 rotate-[-1deg]">
            <Activity className="w-3.5 h-3.5 animate-pulse" />
            <span>Real-Time Engine Observability</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-black text-black tracking-tight uppercase">
            System Observability
          </h1>
          <p className="text-sm sm:text-base font-bold text-gray-700 mt-2 max-w-2xl">
            Live telemetry monitoring for L1/L2 cache hit ratios, async batch queues, sub-millisecond latencies, and rate limit triggers.
          </p>
        </div>

        {/* Live Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`btn-brutal text-xs py-2 px-3.5 flex items-center gap-2 ${
              autoRefresh ? "bg-brutal-yellow text-black" : "bg-white text-black"
            }`}
          >
            <span className={`w-2.5 h-2.5 rounded-full border border-black ${autoRefresh ? "bg-emerald-500 animate-ping" : "bg-gray-400"}`} />
            <span>{autoRefresh ? "LIVE POLLING (2.5s)" : "POLLING PAUSED"}</span>
          </button>

          <button
            onClick={fetchTelemetry}
            className="btn-brutal bg-white hover:bg-brutal-paper text-black text-xs py-2 px-3 flex items-center gap-1.5"
            title="Refresh now"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="card-brutal bg-red-100 p-4 mb-6 flex items-center gap-3 text-black font-bold text-sm">
          <AlertOctagon className="w-5 h-5 text-red-600 flex-shrink-0" />
          <span>Observability Gateway: {error}. Ensure backend is running on port 8000.</span>
        </div>
      )}

      {loading && !data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="card-brutal p-6 bg-white animate-pulse space-y-4">
              <div className="h-6 bg-gray-200 rounded w-1/3"></div>
              <div className="h-8 bg-gray-200 rounded w-3/4"></div>
            </div>
          ))}
        </div>
      ) : data ? (
        <div className="space-y-6">
          {/* Top Status Banner */}
          <div className="card-brutal p-4 bg-white flex flex-wrap items-center justify-between gap-4 text-xs font-bold text-black font-mono">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-emerald-500 border border-black inline-block animate-pulse"></span>
              <span className="uppercase">STATUS: {data.status}</span>
            </div>
            <div>UPTIME: {formatUptime(data.uptime_seconds)}</div>
            <div>LAST SYNC: {new Date(data.timestamp).toLocaleTimeString()}</div>
            <div>
              ENGINE: <span className="bg-brutal-yellow px-2 py-0.5 rounded border border-black">FastAPI Cluster</span>
            </div>
          </div>

          {/* 4 Core Pillars Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* 1. CACHE PERFORMANCE */}
            <div className="card-brutal p-6 bg-white flex flex-col justify-between hover:shadow-brutal-lg transition-all">
              <div>
                {/* Header Row */}
                <div className="flex items-center justify-between h-11 mb-3">
                  <div className="p-2 rounded-xl bg-brutal-green border-2 border-black shadow-brutal-sm flex items-center justify-center">
                    <Zap className="w-5 h-5 text-black" />
                  </div>
                  <span className="badge-brutal bg-brutal-paper text-black text-[11px] whitespace-nowrap h-7 flex items-center">
                    {data.cache.is_redis_active ? "REDIS-L2" : "IN-MEMORY"}
                  </span>
                </div>

                {/* Title */}
                <div className="text-xs font-black uppercase tracking-wider text-gray-500 h-5 flex items-center">
                  Cache Hit Rate
                </div>

                {/* Main Metric Value */}
                <div className="h-10 flex items-baseline gap-1.5 mt-1 mb-2">
                  <span className="text-3xl sm:text-4xl font-black text-black font-mono">
                    {data.cache.hit_rate_pct}%
                  </span>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-gray-200 border-2 border-black rounded-full h-3 mb-3 overflow-hidden">
                  <div 
                    className="bg-brutal-green h-full border-r-2 border-black transition-all duration-500"
                    style={{ width: `${Math.min(data.cache.hit_rate_pct, 100)}%` }}
                  />
                </div>

                {/* 3 Detail Lines */}
                <div className="space-y-1.5 text-xs font-mono font-bold pt-3 border-t-2 border-black/10">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Cache Hits:</span>
                    <span className="text-black font-black">{data.cache.hits}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Cache Misses:</span>
                    <span className="text-black font-black">{data.cache.misses}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">404 Negatives:</span>
                    <span className="text-amber-700 font-black">{data.cache.negative_hits}</span>
                  </div>
                </div>
              </div>

              {/* Pinned Bottom Footer */}
              <div className="mt-4 pt-3 border-t-2 border-black text-[11px] font-bold text-gray-600 flex justify-between items-center h-8">
                <span>Hot In-Memory Keys</span>
                <span className="bg-brutal-yellow px-2 py-0.5 rounded border border-black font-mono font-black text-black">
                  {data.cache.items_in_l1}
                </span>
              </div>
            </div>

            {/* 2. ASYNC EVENT QUEUE */}
            <div className="card-brutal p-6 bg-white flex flex-col justify-between hover:shadow-brutal-lg transition-all">
              <div>
                {/* Header Row */}
                <div className="flex items-center justify-between h-11 mb-3">
                  <div className="p-2 rounded-xl bg-brutal-purple border-2 border-black shadow-brutal-sm flex items-center justify-center">
                    <Layers className="w-5 h-5 text-black" />
                  </div>
                  <span className="badge-brutal bg-brutal-paper text-black text-[11px] whitespace-nowrap h-7 flex items-center">
                    {data.queue.is_worker_running ? "RUNNING" : "STOPPED"}
                  </span>
                </div>

                {/* Title */}
                <div className="text-xs font-black uppercase tracking-wider text-gray-500 h-5 flex items-center">
                  Buffer Queue Size
                </div>

                {/* Main Metric Value */}
                <div className="h-10 flex items-baseline gap-1.5 mt-1 mb-2">
                  <span className="text-3xl sm:text-4xl font-black text-black font-mono">
                    {data.queue.queue_size}
                  </span>
                  <span className="text-xs font-bold text-gray-500 font-mono">items</span>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-gray-200 border-2 border-black rounded-full h-3 mb-3 overflow-hidden">
                  <div 
                    className="bg-brutal-purple h-full border-r-2 border-black transition-all duration-500"
                    style={{ width: `${Math.min((data.queue.queue_size / 50) * 100, 100)}%` }}
                  />
                </div>

                {/* 3 Detail Lines */}
                <div className="space-y-1.5 text-xs font-mono font-bold pt-3 border-t-2 border-black/10">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Total Enqueued:</span>
                    <span className="text-black font-black">{data.queue.total_enqueued}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Total Flushed:</span>
                    <span className="text-black font-black">{data.queue.total_flushed}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Batch Syncs:</span>
                    <span className="text-black font-black">{data.queue.total_batches}</span>
                  </div>
                </div>
              </div>

              {/* Pinned Bottom Footer */}
              <div className="mt-4 pt-3 border-t-2 border-black text-[11px] font-bold text-gray-600 flex justify-between items-center h-8">
                <span>Last Batch Write</span>
                <span className="font-mono text-black text-[10px] truncate max-w-[120px]">
                  {data.queue.last_flush_time ? new Date(data.queue.last_flush_time).toLocaleTimeString() : "Pending"}
                </span>
              </div>
            </div>

            {/* 3. REQUEST LATENCY */}
            <div className="card-brutal p-6 bg-white flex flex-col justify-between hover:shadow-brutal-lg transition-all">
              <div>
                {/* Header Row */}
                <div className="flex items-center justify-between h-11 mb-3">
                  <div className="p-2 rounded-xl bg-brutal-yellow border-2 border-black shadow-brutal-sm flex items-center justify-center">
                    <Gauge className="w-5 h-5 text-black" />
                  </div>
                  <span className="badge-brutal bg-brutal-paper text-black text-[11px] whitespace-nowrap h-7 flex items-center">
                    {data.latency.total_requests} REQS
                  </span>
                </div>

                {/* Title */}
                <div className="text-xs font-black uppercase tracking-wider text-gray-500 h-5 flex items-center">
                  Avg Request Latency
                </div>

                {/* Main Metric Value */}
                <div className="h-10 flex items-baseline gap-1.5 mt-1 mb-2">
                  <span className="text-3xl sm:text-4xl font-black text-black font-mono">
                    {data.latency.avg_latency_ms}
                  </span>
                  <span className="text-xs font-bold text-gray-500 font-mono">ms</span>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-gray-200 border-2 border-black rounded-full h-3 mb-3 overflow-hidden">
                  <div 
                    className="bg-brutal-yellow h-full border-r-2 border-black transition-all duration-500"
                    style={{ width: `${Math.min((data.latency.avg_latency_ms / 20) * 100, 100)}%` }}
                  />
                </div>

                {/* 3 Detail Lines */}
                <div className="space-y-1.5 text-xs font-mono font-bold pt-3 border-t-2 border-black/10">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">P50 Median:</span>
                    <span className="text-black font-black">{data.latency.p50_latency_ms} ms</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">P95 Tail:</span>
                    <span className="text-emerald-700 font-black">{data.latency.p95_latency_ms} ms</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">P99 Peak:</span>
                    <span className="text-brutal-pink font-black">{data.latency.p99_latency_ms} ms</span>
                  </div>
                </div>
              </div>

              {/* Pinned Bottom Footer */}
              <div className="mt-4 pt-3 border-t-2 border-black text-[11px] font-bold text-gray-600 flex justify-between items-center h-8">
                <span>Traffic Velocity</span>
                <span className="bg-brutal-yellow px-2 py-0.5 rounded border border-black font-mono font-black text-black">
                  {data.latency.requests_per_minute} RPM
                </span>
              </div>
            </div>

            {/* 4. RATE LIMITER & THROTTLING */}
            <div className="card-brutal p-6 bg-white flex flex-col justify-between hover:shadow-brutal-lg transition-all">
              <div>
                {/* Header Row */}
                <div className="flex items-center justify-between h-11 mb-3">
                  <div className="p-2 rounded-xl bg-brutal-pink border-2 border-black shadow-brutal-sm text-white flex items-center justify-center">
                    <ShieldAlert className="w-5 h-5 text-white" />
                  </div>
                  <span className="badge-brutal bg-brutal-paper text-black text-[11px] whitespace-nowrap h-7 flex items-center truncate max-w-[140px]">
                    {data.rate_limiter.backend.includes("Redis") ? "REDIS-ZSET" : "IN-MEMORY"}
                  </span>
                </div>

                {/* Title */}
                <div className="text-xs font-black uppercase tracking-wider text-gray-500 h-5 flex items-center">
                  Throttled Requests
                </div>

                {/* Main Metric Value */}
                <div className="h-10 flex items-baseline gap-1.5 mt-1 mb-2">
                  <span className="text-3xl sm:text-4xl font-black text-black font-mono">
                    {data.rate_limiter.total_blocked}
                  </span>
                  <span className="text-xs font-bold text-gray-500 font-mono">blocks</span>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-gray-200 border-2 border-black rounded-full h-3 mb-3 overflow-hidden">
                  <div 
                    className="bg-brutal-pink h-full border-r-2 border-black transition-all duration-500"
                    style={{ width: `${Math.min(data.rate_limiter.block_rate_pct, 100)}%` }}
                  />
                </div>

                {/* 3 Detail Lines */}
                <div className="space-y-1.5 text-xs font-mono font-bold pt-3 border-t-2 border-black/10">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Total Checked:</span>
                    <span className="text-black font-black">{data.rate_limiter.total_checks}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Block Rate:</span>
                    <span className="text-black font-black">{data.rate_limiter.block_rate_pct}%</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600">Shorten Capped:</span>
                    <span className="text-black font-black">{data.rate_limiter.blocks_by_scope.shorten || 0}</span>
                  </div>
                </div>
              </div>

              {/* Pinned Bottom Footer */}
              <div className="mt-4 pt-3 border-t-2 border-black text-[11px] font-bold text-gray-600 flex justify-between items-center h-8">
                <span>Passcode Throttles</span>
                <span className="bg-amber-100 text-amber-900 px-2 py-0.5 rounded border border-black font-mono font-black">
                  {data.rate_limiter.blocks_by_scope.verify || 0}
                </span>
              </div>
            </div>
          </div>


          {/* Deep-Dive Inspection Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Status Codes & Latency Breakdown */}
            <div className="card-brutal p-6 bg-white">
              <div className="flex items-center justify-between border-b-2 border-black pb-3 mb-4">
                <h3 className="text-lg font-black text-black uppercase flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-brutal-green" />
                  HTTP Response Status Codes
                </h3>
                <span className="badge-brutal bg-brutal-yellow text-black">
                  {data.latency.total_requests} Total
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                <div className="border-2 border-black rounded-xl p-3 bg-emerald-50 text-center shadow-brutal-sm">
                  <div className="text-2xl font-black text-emerald-800 font-mono">
                    {data.latency.status_codes["2xx"] || 0}
                  </div>
                  <div className="text-[10px] font-black uppercase text-emerald-900 mt-0.5">2xx Success</div>
                </div>

                <div className="border-2 border-black rounded-xl p-3 bg-blue-50 text-center shadow-brutal-sm">
                  <div className="text-2xl font-black text-blue-800 font-mono">
                    {data.latency.status_codes["3xx"] || 0}
                  </div>
                  <div className="text-[10px] font-black uppercase text-blue-900 mt-0.5">3xx Redirects</div>
                </div>

                <div className="border-2 border-black rounded-xl p-3 bg-amber-50 text-center shadow-brutal-sm">
                  <div className="text-2xl font-black text-amber-800 font-mono">
                    {data.latency.status_codes["4xx"] || 0}
                  </div>
                  <div className="text-[10px] font-black uppercase text-amber-900 mt-0.5">4xx Client Err</div>
                </div>

                <div className="border-2 border-black rounded-xl p-3 bg-red-50 text-center shadow-brutal-sm">
                  <div className="text-2xl font-black text-red-800 font-mono">
                    {data.latency.status_codes["5xx"] || 0}
                  </div>
                  <div className="text-[10px] font-black uppercase text-red-900 mt-0.5">5xx Server Err</div>
                </div>
              </div>

              <div className="bg-brutal-paper border-2 border-black rounded-xl p-4 text-xs font-mono space-y-2">
                <div className="font-bold text-black border-b border-black pb-1">
                  LATENCY DISTRIBUTION SUMMARY:
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Fastest Request (Min):</span>
                  <span className="font-bold text-black">{data.latency.min_latency_ms} ms</span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Average Request Time:</span>
                  <span className="font-bold text-black">{data.latency.avg_latency_ms} ms</span>
                </div>
                <div className="flex justify-between text-gray-700">
                  <span>Peak Request (Max):</span>
                  <span className="font-bold text-black">{data.latency.max_latency_ms} ms</span>
                </div>
              </div>
            </div>

            {/* Rate-Limit Block Events Feed */}
            <div className="card-brutal p-6 bg-white">
              <div className="flex items-center justify-between border-b-2 border-black pb-3 mb-4">
                <h3 className="text-lg font-black text-black uppercase flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-brutal-pink" />
                  Recent Rate-Limit Triggers
                </h3>
                <span className="badge-brutal bg-brutal-pink text-white">
                  {data.rate_limiter.recent_blocked_events.length} Recorded
                </span>
              </div>

              {data.rate_limiter.recent_blocked_events.length === 0 ? (
                <div className="p-8 text-center bg-brutal-paper border-2 border-black border-dashed rounded-xl">
                  <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
                  <p className="text-xs font-black uppercase text-black">
                    No Throttled Events Detected
                  </p>
                  <p className="text-[11px] font-bold text-gray-500 mt-1">
                    All incoming client requests are currently within allocated tier quotas.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                  {data.rate_limiter.recent_blocked_events.map((ev, idx) => (
                    <div 
                      key={idx}
                      className="border-2 border-black rounded-lg p-2.5 bg-brutal-paper flex items-center justify-between text-xs font-mono"
                    >
                      <div className="flex items-center gap-2">
                        <span className="bg-brutal-pink text-white px-2 py-0.5 rounded font-black text-[10px]">
                          {ev.scope.toUpperCase()}
                        </span>
                        <span className="text-gray-700 font-bold">{ev.client}</span>
                      </div>
                      <span className="text-gray-500 text-[10px]">
                        {new Date(ev.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-4 pt-3 border-t-2 border-black flex justify-between items-center text-xs font-bold">
                <span className="text-gray-600">Rate Limiter Backend:</span>
                <span className="bg-brutal-paper border border-black px-2 py-0.5 rounded font-mono">
                  {data.rate_limiter.backend}
                </span>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
