"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "../../../stores/authStore";

declare global { interface Window { google?: any } }

export default function LoginPage() {
  const router = useRouter();
  const { loginWithCode, isAuthenticated } = useAuthStore();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (isAuthenticated) router.push("/");
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
    if (!google?.accounts?.oauth2) {
      setError("Google Sign-In not loaded. Refresh the page.");
      return;
    }
    setLoading(true);
    google.accounts.oauth2.initCodeClient({
      client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
      scope: "email profile",
      ux_mode: "popup",
      callback: async (resp: any) => {
        if (resp.error) { setError(resp.error); setLoading(false); return; }
        try {
          await loginWithCode(resp.code);
          router.push("/");
        } catch (e: any) { setError(e.message); setLoading(false); }
      },
    }).requestCode();
  }, [router, loginWithCode]);

  return (
    <div className="max-w-sm mx-auto mt-24 text-center">
      <h1 className="text-2xl font-bold mb-2">Try1000</h1>
      <p className="text-gray-400 mb-8">Sign in to design and simulate tactics</p>
      <button
        onClick={handleLogin}
        disabled={loading || !ready}
        className="px-6 py-3 bg-white text-black rounded-lg font-medium hover:bg-gray-200 disabled:opacity-50"
      >
        {!ready ? "Loading..." : loading ? "Signing in..." : "Sign in with Google"}
      </button>
      {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
    </div>
  );
}
