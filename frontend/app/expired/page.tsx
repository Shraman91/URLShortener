"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Clock, Home, Link2Off, ArrowRight } from "lucide-react";
import { Suspense } from "react";

function ExpiredContent() {
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const reason = searchParams.get("reason");

  const getSubtitle = () => {
    if (reason === "clicks") {
      return "This link has reached its maximum allowed number of clicks and is no longer accessible.";
    }
    if (reason === "time") {
      return "This link has passed its expiration date and time.";
    }
    return "This short link has expired and is no longer active.";
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-background">
      <div className="max-w-md w-full space-y-8 bg-white p-10 rounded-2xl shadow-sm border border-border text-center animate-in fade-in zoom-in-95 duration-300">
        
        {/* Icon Header */}
        <div className="relative mx-auto w-20 h-20 bg-amber-50 rounded-full flex items-center justify-center mb-6 border border-amber-100 shadow-inner">
          <Clock className="w-10 h-10 text-amber-600 animate-pulse" />
          <div className="absolute -bottom-1 -right-1 bg-red-500 text-white p-1 rounded-full shadow">
            <Link2Off className="w-4 h-4" />
          </div>
        </div>

        {/* Title and Explanation */}
        <div className="space-y-3">
          <h1 className="text-3xl font-extrabold text-foreground tracking-tight">
            Link Expired
          </h1>
          
          {code && (
            <div className="inline-block bg-muted px-3 py-1 rounded-full text-xs font-mono text-muted-foreground border border-border">
              localhost:8000/{code}
            </div>
          )}

          <p className="text-sm text-muted-foreground leading-relaxed pt-2">
            {getSubtitle()}
          </p>
        </div>

        {/* Informational Card */}
        <div className="bg-amber-50/60 border border-amber-200/60 rounded-xl p-4 text-xs text-amber-800 text-left space-y-1.5">
          <p className="font-semibold flex items-center gap-1.5 text-amber-900">
            Why am I seeing this?
          </p>
          <p className="text-amber-700">
            The creator set an expiration limit (time limit or maximum click limit) on this link for security or privacy reasons.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="pt-4 space-y-3">
          <Link
            href="/"
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl shadow-sm text-sm font-semibold text-primary-foreground bg-primary hover:opacity-90 transition-all"
          >
            <Home className="w-4 h-4" />
            Create Your Own Short Link
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LinkExpiredPage() {
  return (
    <Suspense fallback={<div className="flex justify-center items-center h-64 text-muted-foreground">Loading...</div>}>
      <ExpiredContent />
    </Suspense>
  );
}
