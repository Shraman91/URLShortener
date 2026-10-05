import Link from "next/link";
import { AlertOctagon, ArrowLeft, Globe, Zap, Compass, RefreshCw } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-[calc(100vh-5rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-xl w-full card-brutal p-8 sm:p-12 text-center bg-white relative overflow-hidden">
        {/* Top brutalist bar sticker */}
        <div className="inline-flex items-center gap-2 bg-brutal-yellow badge-brutal mb-6 rotate-[-1deg]">
          <AlertOctagon className="w-4 h-4" />
          <span>HTTP 404 // ERROR DETECTED</span>
        </div>

        {/* Huge 404 Graphic */}
        <div className="relative my-4">
          <div className="text-8xl sm:text-9xl font-black text-black tracking-tighter select-none">
            404
          </div>
          <div className="absolute inset-0 flex items-center justify-center opacity-10">
            <span className="text-8xl sm:text-9xl font-black text-brutal-pink tracking-tighter transform translate-x-1 translate-y-1">
              404
            </span>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-2xl sm:text-3xl font-black text-black uppercase tracking-tight mb-3">
          Short Link Not Found
        </h1>

        <p className="text-sm sm:text-base font-medium text-gray-700 leading-relaxed mb-6 max-w-md mx-auto">
          The short code you requested doesn't exist in our registry, has expired, or reached its maximum click limit.
        </p>

        {/* Diagnostic Box */}
        <div className="bg-brutal-paper border-2 border-black rounded-xl p-4 text-left mb-8 shadow-brutal-sm text-xs font-mono space-y-1.5">
          <div className="flex items-center gap-2 font-bold text-black border-b-2 border-black pb-2 mb-2">
            <Zap className="w-3.5 h-3.5 text-brutal-orange" />
            <span>SYSTEM DIAGNOSTIC</span>
          </div>
          <div className="text-gray-600">• Destination: Unresolved address</div>
          <div className="text-gray-600">• Status: Negative cached to prevent penetration attacks</div>
          <div className="text-gray-600">• Action: Return to directory or create a new link</div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/"
            className="w-full sm:w-auto btn-brutal bg-brutal-yellow text-black flex items-center justify-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Go to Home</span>
          </Link>

          <Link
            href="/links"
            className="w-full sm:w-auto btn-brutal bg-brutal-pink text-white flex items-center justify-center gap-2"
          >
            <Globe className="w-4 h-4" />
            <span>Community Feed</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
