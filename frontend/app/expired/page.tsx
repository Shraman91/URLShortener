"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Clock, ArrowRight, Zap, AlertTriangle, Globe } from "lucide-react";
import { Suspense } from "react";

function ExpiredContent() {
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const reason = searchParams.get("reason");

  const getSubtitle = () => {
    if (reason === "clicks") {
      return "This link reached its maximum click limit set by the author and has been permanently deactivated.";
    }
    if (reason === "time") {
      return "This link passed its scheduled expiration timestamp and is no longer serving redirects.";
    }
    return "This short link has expired and is no longer active.";
  };

  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full card-brutal p-8 sm:p-10 bg-white text-center animate-in zoom-in-95">
        
        {/* Top Badge */}
        <div className="inline-flex items-center gap-2 bg-brutal-orange text-black badge-brutal mb-6 rotate-[-1deg]">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>LINK DEACTIVATED // HTTP 410</span>
        </div>

        <div className="w-16 h-16 bg-red-100 border-3 border-black rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-brutal-sm">
          <Clock className="w-8 h-8 text-red-600" />
        </div>

        <h1 className="text-3xl font-black text-black uppercase tracking-tight">
          Link Expired
        </h1>
        
        {code && (
          <div className="mt-1 mb-4 inline-block bg-brutal-paper border-2 border-black px-3 py-1 rounded-lg text-xs font-mono font-bold">
            localhost:8000/{code}
          </div>
        )}

        <p className="text-sm font-bold text-gray-700 leading-relaxed mb-6">
          {getSubtitle()}
        </p>

        <div className="bg-brutal-paper border-2 border-black rounded-xl p-4 text-xs font-mono text-left mb-6 shadow-brutal-sm space-y-1">
          <div className="font-bold text-black border-b border-black pb-1 mb-1">
            EXPIRED URL POLICY:
          </div>
          <div className="text-gray-600">• Auto-purged from L1 memory cache</div>
          <div className="text-gray-600">• Redirect halted at Gateway stage</div>
        </div>

        {/* Action Buttons */}
        <div className="space-y-3">
          <Link
            href="/"
            className="w-full btn-brutal bg-brutal-yellow hover:bg-yellow-300 text-black text-sm flex items-center justify-center gap-2"
          >
            <Zap className="w-4 h-4 fill-current" />
            <span>Create New Short Link</span>
            <ArrowRight className="w-4 h-4" />
          </Link>

          <Link
            href="/links"
            className="w-full btn-brutal bg-white hover:bg-brutal-paper text-black text-sm flex items-center justify-center gap-2"
          >
            <Globe className="w-4 h-4" />
            <span>Browse Community Directory</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LinkExpiredPage() {
  return (
    <Suspense fallback={
      <div className="flex justify-center items-center h-64">
        <div className="badge-brutal bg-brutal-yellow text-black animate-pulse text-sm">
          CHECKING EXPIRATION...
        </div>
      </div>
    }>
      <ExpiredContent />
    </Suspense>
  );
}
