"use client";

import { useEffect } from "react";
import { useAuthStore } from "../../stores/authStore";

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const checkSession = useAuthStore((s) => s.checkSession);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  return <>{children}</>;
}
