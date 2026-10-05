"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { 
  Globe, 
  Search, 
  ExternalLink, 
  Copy, 
  Check, 
  QrCode, 
  Lock, 
  Unlock, 
  Clock, 
  TrendingUp, 
  RefreshCw, 
  Plus, 
  X,
  ShieldCheck,
  AlertCircle,
  Zap
} from "lucide-react";
import { getPublicLinks, URLData } from "../api-client";

export default function CommunityLinksPage() {
  const [links, setLinks] = useState<URLData[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<"all" | "open" | "protected">("all");
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [selectedQr, setSelectedQr] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchLinks = async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    setError(null);
    try {
      const data = await getPublicLinks(100);
      setLinks(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Unable to fetch community links. Please try again.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchLinks();
  }, []);

  const handleCopy = (code: string) => {
    const fullUrl = `http://localhost:8000/${code}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const filteredLinks = useMemo(() => {
    return links.filter((link) => {
      const matchesSearch = 
        link.short_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        link.long_url.toLowerCase().includes(searchQuery.toLowerCase());
      
      if (!matchesSearch) return false;

      if (filterType === "open") return !link.is_password_protected;
      if (filterType === "protected") return link.is_password_protected;
      return true;
    });
  }, [links, searchQuery, filterType]);

  const totalClicks = useMemo(() => {
    return links.reduce((sum, item) => sum + (item.clicks || 0), 0);
  }, [links]);

  const protectedCount = useMemo(() => {
    return links.filter((item) => item.is_password_protected).length;
  }, [links]);

  return (
    <div className="max-w-6xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
      {/* Top Hero Banner */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 bg-brutal-green badge-brutal mb-3 rotate-[-1deg] text-black">
            <Globe className="w-3.5 h-3.5" />
            <span>Public Link Feed</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-black text-black tracking-tight uppercase">
            Community Directory
          </h1>
          <p className="text-sm sm:text-base font-bold text-gray-700 mt-2 max-w-2xl">
            Live directory of short links generated across the network. Password-protected destinations prompt for passcodes upon entry.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchLinks(true)}
            disabled={refreshing}
            className="btn-brutal bg-white hover:bg-brutal-paper text-black text-sm flex items-center gap-2 disabled:opacity-60"
            title="Refresh links"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin text-black" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
          <Link
            href="/"
            className="btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-sm flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span>Shorten New</span>
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="card-brutal p-5 bg-brutal-yellow">
          <div className="text-3xl font-black text-black font-mono">{links.length}</div>
          <div className="text-xs font-black uppercase tracking-wider text-black mt-1">Total Public Links</div>
        </div>

        <div className="card-brutal p-5 bg-brutal-green">
          <div className="text-3xl font-black text-black font-mono">{totalClicks}</div>
          <div className="text-xs font-black uppercase tracking-wider text-black mt-1">Total Redirect Clicks</div>
        </div>

        <div className="card-brutal p-5 bg-brutal-pink text-white">
          <div className="text-3xl font-black text-white font-mono">{protectedCount}</div>
          <div className="text-xs font-black uppercase tracking-wider text-white mt-1">Passcode Locked Links</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card-brutal p-4 mb-6 bg-white flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-black" />
          <input
            type="text"
            placeholder="Search code or destination URL..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-8 py-2.5 border-2 border-black rounded-xl text-sm font-bold text-black focus:outline-none focus:bg-amber-50/40"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-black hover:text-brutal-pink"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <button
            onClick={() => setFilterType("all")}
            className={`btn-brutal text-xs py-1.5 px-3 uppercase ${
              filterType === "all" ? "bg-brutal-yellow text-black" : "bg-white text-black"
            }`}
          >
            All ({links.length})
          </button>
          <button
            onClick={() => setFilterType("open")}
            className={`btn-brutal text-xs py-1.5 px-3 uppercase flex items-center gap-1.5 ${
              filterType === "open" ? "bg-brutal-green text-black" : "bg-white text-black"
            }`}
          >
            <Unlock className="w-3.5 h-3.5" />
            Open ({links.length - protectedCount})
          </button>
          <button
            onClick={() => setFilterType("protected")}
            className={`btn-brutal text-xs py-1.5 px-3 uppercase flex items-center gap-1.5 ${
              filterType === "protected" ? "bg-brutal-pink text-white" : "bg-white text-black"
            }`}
          >
            <Lock className="w-3.5 h-3.5" />
            Protected ({protectedCount})
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="card-brutal bg-red-100 p-4 mb-6 flex items-center gap-3 text-black font-bold text-sm">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Skeleton Loading */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="card-brutal p-6 bg-white animate-pulse space-y-4">
              <div className="h-6 bg-gray-200 rounded w-1/3"></div>
              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
            </div>
          ))}
        </div>
      ) : filteredLinks.length === 0 ? (
        /* Empty State */
        <div className="card-brutal p-12 bg-white text-center">
          <div className="w-16 h-16 bg-brutal-yellow border-2 border-black rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-brutal-sm">
            <Globe className="w-8 h-8 text-black" />
          </div>
          <h3 className="text-xl font-black text-black uppercase mb-1">
            {searchQuery ? "No matching links found" : "Directory Empty"}
          </h3>
          <p className="text-gray-600 font-bold text-sm max-w-md mx-auto mb-6">
            {searchQuery
              ? "Try refining your search keyword or switching your filter category."
              : "Be the first to generate and share a shortened link with the community!"}
          </p>
          <Link
            href="/"
            className="btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-sm inline-flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span>Create First Link</span>
          </Link>
        </div>
      ) : (
        /* Links Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredLinks.map((link) => {
            const fullShortUrl = `http://localhost:8000/${link.short_code}`;
            const isProtected = link.is_password_protected;

            return (
              <div
                key={link.short_code}
                className="card-brutal p-5 bg-white flex flex-col justify-between hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-brutal-lg transition-all"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <a
                          href={fullShortUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xl font-black text-black font-mono hover:text-brutal-pink flex items-center gap-1.5 transition-colors"
                        >
                          /{link.short_code}
                          <ExternalLink className="w-4 h-4 opacity-50" />
                        </a>

                        {isProtected ? (
                          <span className="badge-brutal bg-brutal-pink text-white flex items-center gap-1">
                            <Lock className="w-3 h-3" />
                            Passcode Required
                          </span>
                        ) : (
                          <span className="badge-brutal bg-brutal-green text-black flex items-center gap-1">
                            <Unlock className="w-3 h-3" />
                            Public Open
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button
                        onClick={() => handleCopy(link.short_code)}
                        className="p-2 border-2 border-black rounded-lg bg-brutal-paper hover:bg-brutal-yellow shadow-brutal-sm transition-all"
                        title="Copy short link"
                      >
                        {copiedCode === link.short_code ? (
                          <Check className="w-4 h-4 text-black" />
                        ) : (
                          <Copy className="w-4 h-4 text-black" />
                        )}
                      </button>
                      <button
                        onClick={() => setSelectedQr(link.short_code)}
                        className="p-2 border-2 border-black rounded-lg bg-brutal-paper hover:bg-brutal-blue shadow-brutal-sm transition-all"
                        title="View QR Code"
                      >
                        <QrCode className="w-4 h-4 text-black" />
                      </button>
                    </div>
                  </div>

                  {/* Destination preview */}
                  <div className="my-3">
                    {isProtected ? (
                      <div className="p-3 rounded-xl border-2 border-black bg-amber-50 text-xs font-bold text-black flex items-center gap-2 shadow-brutal-sm">
                        <ShieldCheck className="w-4 h-4 text-amber-700 flex-shrink-0" />
                        <span className="truncate">
                          Passcode protected. Click Visit to unlock destination.
                        </span>
                      </div>
                    ) : (
                      <p className="text-xs font-mono font-bold text-gray-700 truncate bg-brutal-paper border-2 border-black px-3 py-2 rounded-xl shadow-brutal-sm" title={link.long_url}>
                        {link.long_url}
                      </p>
                    )}
                  </div>
                </div>

                {/* Card Footer */}
                <div className="pt-3 mt-2 border-t-2 border-black flex items-center justify-between text-xs font-bold text-black">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1 font-mono">
                      <Clock className="w-3.5 h-3.5" />
                      {new Date(link.created_at).toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-1 font-mono bg-brutal-yellow px-2 py-0.5 rounded border border-black">
                      <TrendingUp className="w-3.5 h-3.5 text-black" />
                      {link.clicks} clicks
                    </span>
                  </div>

                  <a
                    href={fullShortUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="btn-brutal bg-black text-white hover:bg-gray-800 text-xs py-1.5 px-3 inline-flex items-center gap-1.5"
                  >
                    <span>VISIT</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* QR Code Modal */}
      {selectedQr && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in"
          onClick={() => setSelectedQr(null)}
        >
          <div 
            className="card-brutal p-6 sm:p-8 max-w-sm w-full bg-white relative text-center shadow-brutal-xl animate-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setSelectedQr(null)}
              className="absolute right-4 top-4 p-1.5 border-2 border-black rounded-lg bg-brutal-paper hover:bg-brutal-pink text-black transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="inline-block p-3 rounded-2xl bg-brutal-yellow border-2 border-black shadow-brutal-sm mb-4">
              <QrCode className="w-8 h-8 text-black" />
            </div>

            <h3 className="text-xl font-black text-black uppercase">Scan QR Code</h3>
            <p className="text-xs font-bold text-gray-600 mt-1 mb-6 font-mono">
              localhost:8000/{selectedQr}
            </p>

            <div className="border-3 border-black rounded-2xl p-4 bg-brutal-paper inline-block shadow-brutal mb-6">
              <img
                src={`http://localhost:8000/api/qr/${selectedQr}`}
                alt={`QR Code for ${selectedQr}`}
                className="w-48 h-48 mx-auto"
              />
            </div>

            <div className="flex gap-2">
              <a
                href={`http://localhost:8000/api/qr/${selectedQr}`}
                download={`qr-${selectedQr}.png`}
                target="_blank"
                rel="noreferrer"
                className="flex-1 btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-sm py-2.5 flex items-center justify-center gap-1.5"
              >
                Download QR
              </a>
              <button
                onClick={() => setSelectedQr(null)}
                className="btn-brutal bg-white hover:bg-brutal-paper text-black text-sm py-2.5 px-4"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
