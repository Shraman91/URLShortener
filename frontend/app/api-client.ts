const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function shortenUrl(longUrl: string, customAlias?: string) {
  const res = await fetch(`${API_URL}/api/shorten`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ long_url: longUrl, custom_alias: customAlias || null }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Something went wrong");
  }

  return res.json();
}
