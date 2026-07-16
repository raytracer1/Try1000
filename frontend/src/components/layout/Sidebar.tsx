"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "../../stores/authStore";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/tactics", label: "Tactics" },
  { href: "/simulation", label: "Simulation" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuthStore();

  return (
    <aside className="w-56 bg-stone-100 border-r border-stone-200 flex flex-col h-full">
      <div className="p-4">
        <Link href="/" className="text-xl font-bold whitespace-nowrap"><span className="text-green-700">Try</span><span className="text-stone-800">1000</span></Link>
      </div>

      <nav className="flex-1 px-2 py-1 space-y-1">
        {NAV.map(({ href, label }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`block px-3 py-2 rounded text-sm font-medium transition-colors ${
                active ? "bg-green-700 text-white" : "text-stone-600 hover:text-stone-900 hover:bg-stone-200"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-stone-200">
        {isAuthenticated ? (
          <div className="flex items-center justify-between">
            <span className="text-sm text-stone-500 truncate">{user?.username}</span>
            <button onClick={logout} className="text-xs text-stone-400 hover:text-red-600">Logout</button>
          </div>
        ) : (
          <Link href="/auth/login" className="text-sm text-green-700 font-medium">Sign In</Link>
        )}
      </div>
    </aside>
  );
}
