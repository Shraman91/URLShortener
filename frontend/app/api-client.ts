const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface URLData {
  short_code: string;
  long_url: string;
  created_at: string;
  clicks: number;
  expires_at?: string;
  max_clicks?: number;
  is_password_protected: boolean;
  owner_uid?: string;
  safety_score?: number;
  safety_verdict?: string;
  ai_category?: string;
  safety_flags?: string[];
}

export interface AIScanResult {
  url: string;
  safety_score: number;
  safety_verdict: string;
  category: string;
  flags: string[];
  entropy: number;
}

export async function shortenUrl(longUrl: string, customAlias?: string, password?: string) {
  const res = await fetch(`${API_URL}/api/shorten`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      long_url: longUrl,
      custom_alias: customAlias || null,
      password: password || null,
    }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Something went wrong");
  }

  return res.json();
}

export async function scanUrl(url: string): Promise<AIScanResult> {
  const res = await fetch(`${API_URL}/api/scan?url=${encodeURIComponent(url)}`, {
    method: "POST",
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to scan URL");
  }

  return res.json();
}

export async function getPublicLinks(limit: number = 50): Promise<URLData[]> {
  const res = await fetch(`${API_URL}/api/public-links?limit=${limit}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to load community links");
  }

  const data = await res.json();
  return data.urls || [];
}

