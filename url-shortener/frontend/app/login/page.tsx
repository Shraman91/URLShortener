"use client";

import { useState } from "react";
import { signInWithEmailAndPassword, createUserWithEmailAndPassword, signInWithPopup } from "firebase/auth";
import { auth, googleProvider } from "../../lib/firebase";
import { useRouter } from "next/navigation";
import { LogIn, UserPlus, AlertCircle, Zap } from "lucide-react";

export default function LoginPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isLogin) {
        await signInWithEmailAndPassword(auth, email, password);
      } else {
        await createUserWithEmailAndPassword(auth, email, password);
      }
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleAuth = async () => {
    setError("");
    try {
      await signInWithPopup(auth, googleProvider);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full card-brutal p-8 sm:p-10 bg-white relative animate-in zoom-in-95">
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2 bg-brutal-yellow badge-brutal mb-3 rotate-[-1deg] text-black">
            <Zap className="w-3.5 h-3.5 fill-current" />
            <span>ACCOUNT AUTHENTICATION</span>
          </div>

          <h2 className="text-3xl font-black text-black uppercase tracking-tight">
            {isLogin ? "Welcome Back" : "Create Account"}
          </h2>
          <p className="mt-1 text-sm font-bold text-gray-600">
            Sign in to access your personal dashboard and inspect analytics.
          </p>
        </div>
        
        <button
          onClick={handleGoogleAuth}
          className="w-full btn-brutal bg-white hover:bg-brutal-paper text-black text-sm flex items-center justify-center gap-3 py-3"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M21.35,11.1H12.18V13.83H18.69C18.36,17.64 15.19,19.27 12.19,19.27C8.36,19.27 5,16.25 5,12C5,7.9 8.2,4.73 12.2,4.73C15.29,4.73 17.1,6.7 17.1,6.7L19,4.72C19,4.72 16.56,2 12.1,2C6.42,2 2.03,6.8 2.03,12C2.03,17.05 6.16,22 12.25,22C17.6,22 21.5,18.33 21.5,12.91C21.5,11.76 21.35,11.1 21.35,11.1V11.1Z"
            />
          </svg>
          <span>Continue with Google</span>
        </button>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t-2 border-black" />
          </div>
          <div className="relative flex justify-center text-xs font-black uppercase">
            <span className="px-3 bg-white text-black border-2 border-black rounded-lg">
              OR EMAIL
            </span>
          </div>
        </div>

        <form className="space-y-4" onSubmit={handleEmailAuth}>
          <div>
            <label className="block text-xs font-black uppercase text-black mb-1">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border-2 border-black rounded-xl px-4 py-2.5 text-sm font-bold text-black focus:outline-none focus:bg-amber-50/40"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-xs font-black uppercase text-black mb-1">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border-2 border-black rounded-xl px-4 py-2.5 text-sm font-bold text-black focus:outline-none focus:bg-amber-50/40"
              placeholder="••••••••••••"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-100 border-2 border-black rounded-xl text-black font-bold text-xs shadow-brutal-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-sm py-3 flex items-center justify-center gap-2 disabled:opacity-50 mt-2"
          >
            {isLogin ? <LogIn className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
            <span>{loading ? "Processing..." : isLogin ? "Sign In" : "Sign Up"}</span>
          </button>
        </form>
        
        <div className="text-center mt-6 pt-4 border-t-2 border-black">
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-xs font-black uppercase tracking-wide text-black hover:text-brutal-pink transition-colors"
          >
            {isLogin ? "Need an account? → Sign up here" : "Already registered? → Sign in here"}
          </button>
        </div>
      </div>
    </div>
  );
}
