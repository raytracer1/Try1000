"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "../../../stores/authStore";

declare global {
  interface Window { google?: any }
}

export default function LoginPage() {
  const router = useRouter();
  const { loginWithGoogle, isAuthenticated } = useAuthStore();
  const [error, setError] = useState("");

  useEffect(() => {
    if (isAuthenticated) router.push("/");
  }, [isAuthenticated, router]);

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => {
      window.google?.accounts.id.initialize({
        client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
        callback: async (resp: any) => {
          try {
            await loginWithGoogle(resp.credential);
            router.push("/");
          } catch (e: any) { setError(e.message); }
        },
      });
      window.google?.accounts.id.renderButton(
        document.getElementById("googleBtn"),
        { theme: "filled_black", size: "large", width: "320" }
      );
    };
    document.body.appendChild(script);
  }, [router, loginWithGoogle]);

  return (
    <div className="max-w-sm mx-auto mt-24 text-center">
      <h1 className="text-2xl font-bold mb-2">Try1000</h1>
      <p className="text-gray-400 mb-8">Sign in to design and simulate tactics</p>
      <div id="googleBtn" className="flex justify-center mb-4" />
      {error && <p className="text-red-400 text-sm">{error}</p>}
    </div>
  );
}
