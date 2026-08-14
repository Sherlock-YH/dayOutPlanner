"use client";

import { useEffect, useRef, useCallback } from "react";

interface UseAutoLogoutProps {
  /** Timeout duration in minutes before automatically logging out (default: 15) */
  timeoutInMinutes?: number;
  /** Callback function executed when timeout triggers */
  onLogout: () => void;
  /** Only activate the idle timer when user is authenticated */
  isEnabled: boolean;
}

export function useAutoLogout({
  timeoutInMinutes = 15,
  onLogout,
  isEnabled,
}: UseAutoLogoutProps) {
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const handleLogout = useCallback(() => {
    onLogout();
  }, [onLogout]);

  const resetTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    const timeoutInMs = timeoutInMinutes * 60 * 1000;

    timerRef.current = setTimeout(() => {
      handleLogout();
    }, timeoutInMs);
  }, [timeoutInMinutes, handleLogout]);

  useEffect(() => {
    if (!isEnabled) {
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    // Interaction events that count as user activity
    const events: (keyof WindowEventMap)[] = [
      "mousemove",
      "keydown",
      "click",
      "scroll",
      "touchstart",
    ];

    // Throttle resets to avoid excessive timer recalculations on rapid mouse movement
    let lastReset = Date.now();
    const handleUserActivity = () => {
      const now = Date.now();
      if (now - lastReset > 2000) {
        lastReset = now;
        resetTimer();
      }
    };

    events.forEach((event) => {
      window.addEventListener(event, handleUserActivity);
    });

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        resetTimer();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    resetTimer();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);

      events.forEach((event) => {
        window.removeEventListener(event, handleUserActivity);
      });
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isEnabled, resetTimer]);
}