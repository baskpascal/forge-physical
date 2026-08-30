"use client";

import { useEffect, useState } from "react";
import { collection, doc, onSnapshot, orderBy, query } from "firebase/firestore";
import { firebaseConfigured, firestoreDb } from "@/lib/firebase";
import type { Build, Event } from "@/types/build";

export function useBuildStream(buildId: string) {
  const [build, setBuild] = useState<Build | null>(null);
  const [error, setError] = useState<string | null>(null);
  const transport: "firestore" | "api" = firebaseConfigured ? "firestore" : "api";

  useEffect(() => {
    if (firebaseConfigured) {
      const db = firestoreDb();
      if (!db) return;
      let events: Event[] = [];
      const unsubscribeBuild = onSnapshot(doc(db, "builds", buildId), (snapshot) => {
        if (!snapshot.exists()) return setError("Build not found");
        setBuild({ ...(snapshot.data() as Omit<Build, "events">), events });
      }, (caught) => setError(caught.message));
      const unsubscribeEvents = onSnapshot(query(collection(db, "builds", buildId, "events"), orderBy("created_at")), (snapshot) => {
        events = snapshot.docs.map((entry) => entry.data() as Event);
        setBuild((current) => current ? { ...current, events } : current);
      }, (caught) => setError(caught.message));
      return () => { unsubscribeBuild(); unsubscribeEvents(); };
    }

    const controller = new AbortController();
    const base = process.env.NEXT_PUBLIC_BUILD_API_URL ?? "http://127.0.0.1:8080";
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const response = await fetch(`${base}/api/builds/${buildId}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(response.status === 404 ? "Build not found" : `Build API returned ${response.status}`);
        const value = (await response.json()) as Build;
        setBuild(value);
        setError(null);
        if (!["completed", "failed", "needs_review", "unsupported_scope"].includes(value.status)) timer = setTimeout(poll, 1100);
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(caught instanceof Error ? caught.message : "Build stream disconnected");
        timer = setTimeout(poll, 2500);
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [buildId]);

  return { build, error, transport };
}
