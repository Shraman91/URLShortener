"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Lock, KeyRound, ShieldAlert, ArrowRight } from "lucide-react";

export default function PasswordPrompt() {
  const params = useParams();
  const code = params.code as string;
  
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`http://localhost:8000/api/verify/${code}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password }),
      });

      const data = await res.json();
      
      if (!res.ok) {
        if (res.status === 410) {
          window.location.href = `/expired?code=${code}`;
          return;
        }
        throw new Error(data.detail || "Invalid password");
      }

      window.location.href = data.url;
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full card-brutal p-8 sm:p-10 bg-white text-center relative animate-in zoom-in-95">
        {/* Top Sticker */}
        <div className="inline-flex items-center gap-2 bg-brutal-pink text-white badge-brutal mb-6 rotate-[-1deg]">
          <Lock className="w-3.5 h-3.5" />
          <span>PASSCODE REQUIRED</span>
        </div>

        <div className="w-16 h-16 bg-brutal-yellow border-3 border-black rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-brutal-sm">
          <KeyRound className="w-8 h-8 text-black" />
        </div>

        <h2 className="text-2xl sm:text-3xl font-black text-black uppercase tracking-tight">
          Protected Short Link
        </h2>
        <div className="mt-1 mb-6 inline-block bg-brutal-paper border-2 border-black px-3 py-1 rounded-lg text-xs font-mono font-bold">
          localhost:8000/{code}
        </div>

        <p className="text-sm font-bold text-gray-700 mb-6">
          The creator secured this short URL with a secret passcode. Enter the password below to decrypt and redirect.
        </p>

        <form className="space-y-4 text-left" onSubmit={handleSubmit}>
          <div>
            <label className="block text-xs font-black uppercase text-black mb-1.5">
              Enter Passcode
            </label>
            <input
              type="password"
              required
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border-3 border-black rounded-xl px-4 py-3 text-base font-bold text-black focus:outline-none focus:bg-amber-50/40 focus:shadow-brutal transition-all"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-100 border-2 border-black rounded-xl text-black font-bold text-xs shadow-brutal-sm flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-sm py-3.5 flex items-center justify-center gap-2 disabled:opacity-50 mt-4"
          >
            {loading ? (
              <span>Verifying Passcode...</span>
            ) : (
              <>
                <span>Unlock & Visit Destination</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
