"use client";

import Link from "next/link";
import { useAuthStore } from "../../stores/authStore";

export function Header() {
  const { isAuthenticated, user, logout } = useAuthStore();

  return (
    <header className="bg-white border-b border-stone-200 px-8 py-4 flex items-center justify-between">
      <Link href="/" className="text-2xl font-bold tracking-tight">
        Try<span className="text-green-700">1000</span>
      </Link>
      <div className="flex items-center gap-4">
        {isAuthenticated ? (
          <>
            <Link href="/dashboard" className="text-sm text-stone-600 hover:text-stone-800 font-medium">Dashboard</Link>
            <span className="text-sm text-stone-400">{user?.username}</span>
            <button onClick={logout} className="text-sm text-stone-500 hover:text-red-600 transition-colors">Logout</button>
          </>
        ) : (
          <>
            <Link href="/auth/login" className="text-sm text-stone-500 hover:text-stone-800 font-medium">Sign In</Link>
            <Link href="/auth/login" className="px-5 py-2.5 bg-green-700 text-white text-sm font-semibold hover:bg-green-800 transition-colors">Start Now</Link>
          </>
        )}
      </div>
    </header>
  );
}
