"use client";

import { useState, useEffect } from "react";

export function useIsMac(): boolean {
  const [isMac, setIsMac] = useState(true);
  useEffect(() => {
    setIsMac(/mac/i.test(navigator.userAgent));
  }, []);
  return isMac;
}

export function modKey(): string {
  if (typeof window === "undefined") return "⌘";
  return /mac/i.test(navigator.userAgent) ? "⌘" : "Ctrl";
}

export function modKeyShort(): string {
  if (typeof window === "undefined") return "⌘";
  return /mac/i.test(navigator.userAgent) ? "⌘" : "Ctrl+";
}
