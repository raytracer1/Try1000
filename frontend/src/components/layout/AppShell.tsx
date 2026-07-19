"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = pathname === "/" || pathname.startsWith("/auth/");

  if (isPublic) {
    return <main className="flex-1 overflow-auto" style={{ scrollbarGutter: "stable" }}>{children}</main>;
  }

  return (
    <>
      <Sidebar />
      <main className="flex-1 overflow-auto p-6" style={{ scrollbarGutter: "stable" }}>{children}</main>
    </>
  );
}
