import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "../components/layout/AppShell";
import { SessionProvider } from "../components/layout/SessionProvider";

export const metadata: Metadata = {
  title: "Try1000 — AI Football Tactics",
  description: "Design, simulate, and optimize football tactics",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full text-stone-800 flex" style={{ background: "#f5f2ed" }}>
        <SessionProvider>
          <AppShell>{children}</AppShell>
        </SessionProvider>
      </body>
    </html>
  );
}
