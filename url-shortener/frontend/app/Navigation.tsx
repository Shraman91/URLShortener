"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { Link as LinkIcon, LogIn, LogOut, LayoutDashboard, Globe, Zap } from "lucide-react";

export default function Navigation() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <nav className="border-b-3 border-black bg-white sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-20 items-center">
          {/* Logo */}
          <div className="flex items-center gap-6">
            <Link 
              href="/" 
              className="flex items-center gap-2.5 group hover:translate-x-[-1px] hover:translate-y-[-1px] transition-transform"
            >
              <div className="p-2.5 rounded-xl bg-brutal-yellow border-2 border-black shadow-brutal-sm group-hover:bg-brutal-pink transition-colors">
                <Zap className="w-5 h-5 text-black" />
              </div>
              <span className="font-black text-2xl tracking-tighter text-black uppercase">
                SHORTR<span className="text-brutal-pink">.</span>
              </span>
            </Link>

            {/* Nav Links */}
            <div className="hidden sm:flex items-center gap-3">
              <Link 
                href="/"
                className={`px-3.5 py-1.5 rounded-xl text-sm font-extrabold uppercase tracking-wide border-2 transition-all ${
                  pathname === "/" 
                    ? "bg-brutal-yellow border-black shadow-brutal-sm text-black" 
                    : "border-transparent text-black/80 hover:border-black hover:bg-brutal-paper"
                }`}
              >
                Shorten
              </Link>
              <Link 
                href="/links"
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-sm font-extrabold uppercase tracking-wide border-2 transition-all ${
                  pathname === "/links" || pathname === "/community"
                    ? "bg-brutal-green border-black shadow-brutal-sm text-black" 
                    : "border-transparent text-black/80 hover:border-black hover:bg-brutal-paper"
                }`}
              >
                <Globe className="w-4 h-4" />
                Community
              </Link>
              <Link 
                href="/system"
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-sm font-extrabold uppercase tracking-wide border-2 transition-all ${
                  pathname === "/system"
                    ? "bg-brutal-purple border-black shadow-brutal-sm text-black" 
                    : "border-transparent text-black/80 hover:border-black hover:bg-brutal-paper"
                }`}
              >
                <Zap className="w-4 h-4" />
                System
              </Link>
              {user && (
                <Link 
                  href="/dashboard"
                  className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-sm font-extrabold uppercase tracking-wide border-2 transition-all ${
                    pathname === "/dashboard" 
                      ? "bg-brutal-pink border-black shadow-brutal-sm text-white" 
                      : "border-transparent text-black/80 hover:border-black hover:bg-brutal-paper"
                  }`}
                >
                  <LayoutDashboard className="w-4 h-4" />
                  Dashboard
                </Link>
              )}
            </div>
          </div>

          {/* Right Profile / Auth Actions */}
          <div className="flex items-center gap-3">
            <Link
              href="/links"
              className="sm:hidden flex items-center gap-1 text-xs font-bold border-2 border-black px-2.5 py-1 rounded-lg bg-brutal-green shadow-brutal-sm text-black"
            >
              <Globe className="w-3.5 h-3.5" />
              Links
            </Link>

            {user ? (
              <div className="flex items-center gap-3">
                <span className="hidden md:inline-block border-2 border-black bg-brutal-paper px-3 py-1 rounded-lg text-xs font-mono font-bold text-black shadow-brutal-sm truncate max-w-[160px]">
                  {user.email}
                </span>
                <button 
                  onClick={logout}
                  className="flex items-center gap-1.5 btn-brutal bg-white hover:bg-red-100 text-xs text-black"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Sign Out</span>
                </button>
              </div>
            ) : (
              <Link 
                href="/login"
                className="flex items-center gap-2 btn-brutal bg-brutal-yellow text-black text-sm"
              >
                <LogIn className="w-4 h-4" />
                <span>Sign In</span>
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}


