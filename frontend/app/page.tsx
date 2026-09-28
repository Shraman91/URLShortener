"use client";

import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Link2, QrCode, Settings2, Download } from "lucide-react";

export default function Home() {
  const { token } = useAuth();
  
  const [longUrl, setLongUrl] = useState("");
  const [alias, setAlias] = useState("");
  const [password, setPassword] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [maxClicks, setMaxClicks] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const [result, setResult] = useState<{ short_url: string, short_code: string } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
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
    
    try {
      const payload: any = { long_url: longUrl };
      if (alias) payload.custom_alias = alias;
      if (password) payload.password = password;
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

  return (
    <main className="max-w-3xl mx-auto mt-20 p-6">
      <div className="text-center mb-12">
        <h1 className="text-5xl font-extrabold text-primary mb-4 tracking-tight">Make Every Link Count</h1>
        <p className="text-muted-foreground text-lg max-w-xl mx-auto">
          Shorten, personalize, and track your links with our powerful tools. Enhance your digital presence today.
        </p>
      </div>

      <div className="bg-white p-8 rounded-2xl shadow-sm border border-border">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Link2 className="h-5 w-5 text-muted-foreground" />
            </div>
            <input
              type="url"
              placeholder="Paste your long URL here..."
              value={longUrl}
              onChange={(e) => setLongUrl(e.target.value)}
              required
              className="w-full bg-background border border-border rounded-xl pl-12 pr-4 py-4 text-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
            />
          </div>

          <div className="flex items-center justify-between">
            <button 
              type="button" 
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
            >
              <Settings2 className="w-4 h-4" />
              {showAdvanced ? "Hide Advanced Options" : "Show Advanced Options"}
            </button>
            <button 
              type="submit" 
              disabled={loading}
              className="bg-primary text-primary-foreground px-8 py-3 rounded-xl font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 shadow-md"
            >
              {loading ? "Shortening..." : "Shorten URL"}
            </button>
          </div>

          {showAdvanced && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-6 bg-muted rounded-xl border border-border animate-in fade-in slide-in-from-top-4 duration-300">
              <div className="space-y-1">
                <label className="text-sm font-medium text-foreground block">Custom Alias</label>
                <input
                  type="text"
                  placeholder="e.g. my-promo"
                  value={alias}
                  onChange={(e) => setAlias(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-foreground block">Password Protection</label>
                <input
                  type="password"
                  placeholder="Leave blank for public"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-foreground block">Expiration Date</label>
                <input
                  type="datetime-local"
                  value={expiresAt}
                  onChange={(e) => setExpiresAt(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium text-foreground block">Max Clicks</label>
                <input
                  type="number"
                  placeholder="Unlimited"
                  value={maxClicks}
                  onChange={(e) => setMaxClicks(e.target.value)}
                  min="1"
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary"
                />
              </div>
            </div>
          )}
        </form>

        {error && (
          <div className="mt-6 p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-8 p-6 bg-muted border border-border rounded-xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            <h3 className="text-lg font-bold text-foreground mb-4">Your shortened URL is ready!</h3>
            <div className="flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="flex-1 w-full bg-background p-4 rounded-lg border border-border break-all text-primary font-medium text-lg">
                <a href={result.short_url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  {result.short_url}
                </a>
              </div>
              
              {qrCodeData && (
                <div className="flex flex-col items-center gap-2">
                  <div className="bg-white p-2 rounded-lg border border-border shadow-sm">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={qrCodeData} alt="QR Code" className="w-32 h-32" />
                  </div>
                  <a 
                    href={qrCodeData} 
                    download={`qrcode-${result.short_code}.png`}
                    className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-primary transition-colors"
                  >
                    <Download className="w-3 h-3" />
                    Download QR
                  </a>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
