"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "../../../stores/authStore";

declare global { interface Window { google?: any } }

export default function LoginPage() {
  const router = useRouter();
  const { loginWithCode, isAuthenticated } = useAuthStore();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (isAuthenticated) router.push("/dashboard");
  }, [isAuthenticated, router]);

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => setReady(true);
    document.body.appendChild(script);
  }, []);

  const handleLogin = useCallback(() => {
    const google = window.google;
    if (!google?.accounts?.oauth2) { setError("Google Sign-In not loaded."); return; }
    setLoading(true);
    google.accounts.oauth2.initCodeClient({
      client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
      scope: "email profile",
      ux_mode: "popup",
      callback: async (resp: any) => {
        if (resp.error) { setError(resp.error); setLoading(false); return; }
        try { await loginWithCode(resp.code); router.push("/dashboard"); }
        catch (e: any) { setError(e.message); setLoading(false); }
      },
    }).requestCode();
  }, [router, loginWithCode]);

  return (
    <div className="h-full flex items-start justify-center pt-32">
    <div className="p-4 w-full max-w-sm text-center">
      <div className="w-full max-w-sm text-center">
        <Link href="/" className="text-2xl font-bold mb-8 block">
          Try<span className="text-green-700">1000</span>
        </Link>
        <h1 className="text-2xl font-bold text-stone-800 mb-1">Welcome back</h1>
        <p className="text-stone-500 text-sm mb-8">Sign in to continue to your dashboard</p>

        <button onClick={handleLogin} disabled={loading || !ready}
          className="w-full py-3 px-4 bg-white border border-stone-300 rounded-lg text-stone-700 font-medium hover:border-stone-400 disabled:opacity-50 transition-all flex items-center justify-center gap-3 text-base">
          <svg className="w-5 h-5" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
          {!ready ? "Loading..." : loading ? "Signing in..." : "Continue with Google"}
        </button>

        {error && <p className="text-red-600 text-xs mt-4 bg-red-50 border border-red-200 rounded-lg py-2 px-3">{error}</p>}
      </div>
    </div>
    </div>
  );
}
