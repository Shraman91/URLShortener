"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Lock } from "lucide-react";

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
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-background">
      <div className="max-w-md w-full space-y-8 bg-white p-10 rounded-2xl shadow-sm border border-border text-center">
        <div className="mx-auto w-12 h-12 bg-muted rounded-full flex items-center justify-center mb-4">
          <Lock className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-3xl font-extrabold text-foreground">
            Protected Link
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            This URL is password protected. Please enter the password to continue.
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div>
            <input
              type="password"
              required
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="appearance-none block w-full px-3 py-3 border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-primary focus:border-primary sm:text-sm"
            />
          </div>

          {error && <div className="text-red-600 text-sm font-medium">{error}</div>}

          <div>
            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-medium text-primary-foreground bg-primary hover:opacity-90 focus:outline-none transition-opacity disabled:opacity-50"
            >
              {loading ? "Verifying..." : "Access Link"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
