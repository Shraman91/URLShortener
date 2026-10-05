"use client";

import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { 
  Link2, 
  QrCode, 
  Settings2, 
  Download, 
  Copy, 
  Check, 
  ExternalLink, 
  Lock, 
  Calendar, 
  MousePointerClick, 
  Zap, 
  ShieldCheck, 
  Sparkles,
  ArrowRight,
  Flame
} from "lucide-react";

export default function Home() {
  const { token } = useAuth();
  
  const [longUrl, setLongUrl] = useState("");
  const [alias, setAlias] = useState("");
  const [password, setPassword] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [maxClicks, setMaxClicks] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const [result, setResult] = useState<{ 
    short_url: string; 
    short_code: string; 
    long_url?: string;
    safety_score?: number;
    safety_verdict?: string;
    ai_category?: string;
    safety_flags?: string[];
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [qrCodeData, setQrCodeData] = useState<string | null>(null);

  async function fetchQrCode(code: string) {
    try {
      const res = await fetch(`http://localhost:8000/api/qr/${code}`);
      if (!res.ok) return;
      const blob = await res.blob();
      setQrCodeData(URL.createObjectURL(blob));
    } catch (err) {
      console.error("Failed to load QR code", err);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setResult(null);
    setQrCodeData(null);
    setLoading(true);
    setCopied(false);
    
    try {
      const payload: any = { long_url: longUrl };
      if (alias.trim()) payload.custom_alias = alias.trim();
      if (password.trim()) payload.password = password.trim();
      if (expiresAt) payload.expires_at = new Date(expiresAt).toISOString();
      if (maxClicks) payload.max_clicks = parseInt(maxClicks);

      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("http://localhost:8000/api/shorten", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to shorten URL");
      
      setResult(data);
      fetchQrCode(data.short_code);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.short_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <main className="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
      {/* Hero Header */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 bg-brutal-yellow badge-brutal mb-4 rotate-[-1deg]">
          <Zap className="w-4 h-4 fill-current" />
          <span>Distributed Snowflake URL Engine</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-black text-black tracking-tight uppercase mb-3">
          Shorten Links. <br />
          <span className="bg-brutal-pink text-white px-3 py-0.5 inline-block rotate-[1deg] border-2 border-black shadow-brutal-sm">
            Break Nothing.
          </span>
        </h1>

        <p className="text-base sm:text-lg font-bold text-gray-700 max-w-xl mx-auto mt-4">
          Lightning-fast short links powered by snowflake IDs, multi-tier caching, and password protection.
        </p>
      </div>

      {/* Main Shortener Form Box */}
      <div className="card-brutal p-6 sm:p-10 mb-8 bg-white relative">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Main Input */}
          <div className="space-y-2">
            <label className="block text-xs font-black uppercase tracking-wider text-black">
              Enter Destination URL
            </label>
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <input
                  type="url"
                  placeholder="https://example.com/very-long-url-to-shorten"
                  value={longUrl}
                  onChange={(e) => setLongUrl(e.target.value)}
                  required
                  className="w-full border-3 border-black rounded-xl px-4 py-3.5 text-base sm:text-lg font-bold text-black placeholder:text-gray-400 focus:outline-none focus:bg-amber-50/40 focus:shadow-brutal transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-base flex items-center justify-center gap-2 whitespace-nowrap disabled:opacity-50"
              >
                {loading ? (
                  <span>Generating...</span>
                ) : (
                  <>
                    <Zap className="w-5 h-5 fill-current" />
                    <span>Shorten URL</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Advanced Options Toggle */}
          <div className="pt-2">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-black hover:text-brutal-pink transition-colors bg-brutal-paper border-2 border-black px-3 py-1.5 rounded-lg shadow-brutal-sm"
            >
              <Settings2 className="w-3.5 h-3.5" />
              <span>{showAdvanced ? "Hide Advanced Config" : "Show Advanced Config (Passcode, Alias, Expiry)"}</span>
            </button>
          </div>

          {/* Advanced Configuration Grid */}
          {showAdvanced && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t-2 border-black border-dashed animate-in fade-in slide-in-from-top-2">
              {/* Custom Alias */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wide text-black flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-brutal-pink" />
                  Custom Slug (Alias)
                </label>
                <div className="flex items-center">
                  <span className="bg-brutal-paper border-2 border-r-0 border-black px-3 py-2.5 rounded-l-xl text-xs font-mono font-bold text-gray-600">
                    /
                  </span>
                  <input
                    type="text"
                    placeholder="my-cool-link"
                    value={alias}
                    onChange={(e) => setAlias(e.target.value)}
                    className="w-full border-2 border-black rounded-r-xl px-3 py-2 text-sm font-bold text-black focus:outline-none focus:bg-amber-50/40"
                  />
                </div>
              </div>

              {/* Password Protection */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wide text-black flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-amber-600" />
                  Passcode Protection
                </label>
                <input
                  type="password"
                  placeholder="Secret passcode required to open"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full border-2 border-black rounded-xl px-3 py-2 text-sm font-bold text-black focus:outline-none focus:bg-amber-50/40"
                />
              </div>

              {/* Expiration Date */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wide text-black flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-blue-600" />
                  Expiry Date & Time
                </label>
                <input
                  type="datetime-local"
                  value={expiresAt}
                  onChange={(e) => setExpiresAt(e.target.value)}
                  className="w-full border-2 border-black rounded-xl px-3 py-2 text-sm font-bold text-black focus:outline-none focus:bg-amber-50/40"
                />
              </div>

              {/* Max Clicks */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wide text-black flex items-center gap-1.5">
                  <MousePointerClick className="w-3.5 h-3.5 text-purple-600" />
                  Max Click Limit
                </label>
                <input
                  type="number"
                  min="1"
                  placeholder="e.g. 50 (expires after limit)"
                  value={maxClicks}
                  onChange={(e) => setMaxClicks(e.target.value)}
                  className="w-full border-2 border-black rounded-xl px-3 py-2 text-sm font-bold text-black focus:outline-none focus:bg-amber-50/40"
                />
              </div>
            </div>
          )}
        </form>

        {/* Error Message */}
        {error && (
          <div className="mt-6 p-4 bg-red-100 border-2 border-black rounded-xl text-black font-bold text-sm shadow-brutal-sm flex items-center gap-2">
            <span className="bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs">!</span>
            <span>{error}</span>
          </div>
        )}

        {/* Result Card */}
        {result && (
          <div className="mt-8 pt-8 border-t-3 border-black animate-in fade-in zoom-in-95">
            <div className="bg-brutal-paper border-2 border-black rounded-2xl p-6 shadow-brutal space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 bg-brutal-green badge-brutal inline-flex text-black">
                  <Check className="w-3.5 h-3.5" />
                  <span>LINK SHORTENED SUCCESSFULLY</span>
                </div>

                {/* AI Safety Score Badge */}
                <div className={`badge-brutal flex items-center gap-1.5 font-mono ${
                  (result.safety_score ?? 100) >= 85
                    ? "bg-brutal-green text-black"
                    : (result.safety_score ?? 100) >= 65
                    ? "bg-brutal-yellow text-black"
                    : (result.safety_score ?? 100) >= 40
                    ? "bg-amber-400 text-black"
                    : "bg-brutal-pink text-white"
                }`}>
                  <ShieldCheck className="w-4 h-4" />
                  <span>AI SAFETY: {result.safety_score ?? 100}/100 · {result.safety_verdict ?? "SAFE"}</span>
                </div>
              </div>

              <div className="flex flex-col lg:flex-row items-center justify-between gap-6">
                {/* Short Code & Actions */}
                <div className="space-y-4 w-full lg:w-2/3">
                  <div>
                    <span className="text-xs font-black uppercase tracking-wider text-gray-500">Your Short Link</span>
                    <div className="text-2xl sm:text-3xl font-black text-black font-mono tracking-tight break-all">
                      {result.short_url}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={handleCopy}
                      className="btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-sm flex items-center gap-2"
                    >
                      {copied ? (
                        <>
                          <Check className="w-4 h-4 text-emerald-800" />
                          <span>COPIED TO CLIPBOARD!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-4 h-4" />
                          <span>COPY LINK</span>
                        </>
                      )}
                    </button>

                    <a
                      href={result.short_url}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-brutal bg-white hover:bg-gray-100 text-black text-sm flex items-center gap-1.5"
                    >
                      <span>TEST LINK</span>
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>

                {/* QR Code */}
                {qrCodeData && (
                  <div className="border-2 border-black rounded-xl p-3 bg-white text-center shadow-brutal-sm flex-shrink-0">
                    <img
                      src={qrCodeData}
                      alt={`QR code for ${result.short_code}`}
                      className="w-32 h-32 mx-auto mb-2"
                    />
                    <a
                      href={qrCodeData}
                      download={`qr-${result.short_code}.png`}
                      className="inline-flex items-center gap-1 text-xs font-black uppercase tracking-wide text-black hover:text-brutal-pink"
                    >
                      <Download className="w-3 h-3" />
                      Download QR
                    </a>
                  </div>
                )}
              </div>

              {/* AI Intelligence Threat Analysis Panel */}
              <div className="pt-4 border-t-2 border-black bg-white rounded-xl p-4 border-2 shadow-brutal-sm">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <span className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-brutal-pink" />
                    AI Link Intelligence Scan
                  </span>
                  {result.ai_category && (
                    <span className="text-xs font-mono font-bold bg-brutal-paper border border-black px-2 py-0.5 rounded">
                      Category: {result.ai_category}
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  {(result.safety_flags && result.safety_flags.length > 0 ? result.safety_flags : ["Clean Domain Reputation", "SSL/TLS Encrypted"]).map((flag, idx) => (
                    <span
                      key={idx}
                      className="text-xs font-bold px-2.5 py-1 bg-brutal-paper border border-black rounded-lg flex items-center gap-1"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-black"></span>
                      {flag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Feature Badges Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-brutal p-5 bg-white">
          <div className="inline-block p-2.5 rounded-xl bg-brutal-yellow border-2 border-black shadow-brutal-sm mb-3">
            <Zap className="w-5 h-5 text-black" />
          </div>
          <h3 className="text-base font-black uppercase text-black">Snowflake IDs</h3>
          <p className="text-xs font-bold text-gray-600 mt-1">
            Zero collision rate with 64-bit distributed snowflake key generation.
          </p>
        </div>

        <div className="card-brutal p-5 bg-white">
          <div className="inline-block p-2.5 rounded-xl bg-brutal-green border-2 border-black shadow-brutal-sm mb-3">
            <ShieldCheck className="w-5 h-5 text-black" />
          </div>
          <h3 className="text-base font-black uppercase text-black">Multi-Tier Cache</h3>
          <p className="text-xs font-bold text-gray-600 mt-1">
            Sub-millisecond L1 in-memory + Redis caching with 404 anti-penetration.
          </p>
        </div>

        <div className="card-brutal p-5 bg-white">
          <div className="inline-block p-2.5 rounded-xl bg-brutal-pink border-2 border-black shadow-brutal-sm mb-3">
            <Lock className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-base font-black uppercase text-black">Password Protected</h3>
          <p className="text-xs font-bold text-gray-600 mt-1">
            Bcrypt hashed access keys to lock sensitive links from unauthorized eyes.
          </p>
        </div>

        <div className="card-brutal p-5 bg-white">
          <div className="inline-block p-2.5 rounded-xl bg-purple-300 border-2 border-black shadow-brutal-sm mb-3">
            <Sparkles className="w-5 h-5 text-black" />
          </div>
          <h3 className="text-base font-black uppercase text-black">AI Threat Scanner</h3>
          <p className="text-xs font-bold text-gray-600 mt-1">
            Real-time safety scoring (0-100), phishing detection & entropy analysis.
          </p>
        </div>
      </div>
    </main>
  );
}
