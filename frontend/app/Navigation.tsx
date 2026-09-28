"use client";

import Link from "next/link";
import { useAuth } from "../context/AuthContext";
import { Link as LinkIcon, LogIn, LogOut, LayoutDashboard } from "lucide-react";

export default function Navigation() {
  const { user, logout } = useAuth();

  return (
    <nav className="border-b border-border bg-background">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex-shrink-0 flex items-center">
            <Link href="/" className="flex items-center gap-2 text-primary font-bold text-xl transition-opacity hover:opacity-80">
              <LinkIcon className="w-6 h-6" />
              <span>Shortr</span>
            </Link>
          </div>
          <div className="flex items-center gap-4">
            {user ? (
              <>
                <Link 
                  href="/dashboard"
                  className="flex items-center gap-2 text-foreground hover:text-primary transition-colors text-sm font-medium"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  Dashboard
                </Link>
                <button 
                  onClick={logout}
                  className="flex items-center gap-2 bg-muted text-foreground px-3 py-1.5 rounded-md text-sm font-medium hover:bg-border transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </>
            ) : (
              <Link 
                href="/login"
                className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:opacity-90 transition-opacity shadow-sm"
              >
                <LogIn className="w-4 h-4" />
                Sign In
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
