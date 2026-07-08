"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "../../stores/authStore";

const NAV = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/tactics", label: "Tactics", icon: "⚽" },
  { href: "/simulation", label: "Simulation", icon: "▶️" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuthStore();

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col h-full">
      <div className="p-4 border-b border-gray-800">
        <Link href="/" className="text-xl font-bold tracking-tight">
          <span className="text-emerald-400">Try</span>1000
        </Link>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {NAV.map(({ href, label, icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === href
                ? "bg-emerald-500/10 text-emerald-400"
                : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
            }`}
          >
            <span>{icon}</span>
            {label}
          </Link>
        ))}
      </nav>

      <div className="p-3 border-t border-gray-800">
        {isAuthenticated ? (
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400 truncate">{user?.username}</span>
            <button onClick={logout} className="text-xs text-gray-500 hover:text-red-400">
              Logout
            </button>
          </div>
        ) : (
          <Link href="/auth/login" className="text-sm text-emerald-400 hover:underline">
            Sign In
          </Link>
        )}
      </div>
    </aside>
  );
}
