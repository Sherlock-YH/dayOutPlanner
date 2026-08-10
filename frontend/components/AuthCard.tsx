"use client";

import { useState } from "react";

interface AuthCardProps {
  apiBase: string;
  onAuthSuccess: (token: string) => void;
}

export default function AuthCard({ apiBase, onAuthSuccess }: AuthCardProps) {
  const [isSignup, setIsSignup] = useState(false);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Normalize apiBase to avoid double slashes
  const cleanApiBase = apiBase.replace(/\/$/, "");

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);

    // 1. Front-end validation for Signup
    if (isSignup) {
      if (authPassword !== confirmPassword) {
        setAuthError("Passwords do not match.");
        return;
      }
      if (authPassword.length < 8) {
        setAuthError("Password must be at least 8 characters long.");
        return;
      }
    }

    setIsLoading(true);

    const endpoint = isSignup ? "/api/auth/signup" : "/api/auth/login";
    let headers: Record<string, string> = {};
    let body: any;

    if (isSignup) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify({ email: authEmail, password: authPassword });
    } else {
      headers["Content-Type"] = "application/x-www-form-urlencoded";
      const formData = new URLSearchParams();
      formData.append("username", authEmail);
      formData.append("password", authPassword);
      body = formData.toString();
    }

    try {
      const res = await fetch(`${cleanApiBase}${endpoint}`, {
        method: "POST",
        headers,
        body,
      });

      const contentType = res.headers.get("content-type");
      let data: any = {};
      if (contentType && contentType.includes("application/json")) {
        data = await res.json();
      }

      if (!res.ok) {
        throw new Error(data.detail || `Server error (${res.status})`);
      }

      if (isSignup) {
        alert("Account created successfully! Please log in.");
        setIsSignup(false);
        setConfirmPassword("");
      } else {
        if (!data.access_token) {
          throw new Error("No access token returned from server.");
        }
        localStorage.setItem("token", data.access_token);
        onAuthSuccess(data.access_token);
      }
    } catch (err: any) {
      setAuthError(err.message || "An error occurred during authentication.");
    } finally {
      setIsLoading(false);
    }
  };

  const toggleMode = () => {
    setIsSignup(!isSignup);
    setAuthError(null);
    setConfirmPassword("");
  };

  return (
    <main className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-800/90 border border-slate-700 rounded-2xl p-8 space-y-6 shadow-2xl">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-extrabold tracking-tight text-emerald-400">
            🇸🇬 One Day Out Planner
          </h1>
          <p className="text-slate-400 text-sm">
            {isSignup
              ? "Create an account to start planning"
              : "Log in to access your itinerary engine"}
          </p>
        </div>

        {authError && (
          <div className="p-3 bg-red-900/40 border border-red-700 rounded-xl text-red-200 text-xs">
            ⚠️ {authError}
          </div>
        )}

        <form onSubmit={handleAuthSubmit} className="space-y-4">
          <div className="space-y-1.5 text-left">
            <label className="text-xs font-semibold text-slate-400">
              Email Address
            </label>
            <input
              type="email"
              required
              disabled={isLoading}
              value={authEmail}
              onChange={(e) => setAuthEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
            />
          </div>

          <div className="space-y-1.5 text-left">
            <label className="text-xs font-semibold text-slate-400">
              Password
            </label>
            <input
              type="password"
              required
              disabled={isLoading}
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
            />
          </div>

          {/* Confirm Password Field (Signup only) */}
          {isSignup && (
            <div className="space-y-1.5 text-left">
              <label className="text-xs font-semibold text-slate-400">
                Confirm Password
              </label>
              <input
                type="password"
                required
                disabled={isLoading}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-emerald-500 hover:bg-emerald-600 disabled:bg-emerald-800 font-bold text-slate-950 disabled:text-slate-400 py-3 rounded-xl transition-all text-sm cursor-pointer disabled:cursor-not-allowed shadow-lg shadow-emerald-500/10"
          >
            {isLoading ? "Connecting..." : isSignup ? "Sign Up" : "Log In"}
          </button>
        </form>

        <div className="text-center pt-2">
          <button
            type="button"
            disabled={isLoading}
            onClick={toggleMode}
            className="text-xs text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer disabled:opacity-50"
          >
            {isSignup
              ? "Already have an account? Log in"
              : "Need an account? Sign up"}
          </button>
        </div>
      </div>
    </main>
  );
}