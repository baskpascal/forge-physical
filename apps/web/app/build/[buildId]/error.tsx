"use client";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return <main className="error-screen"><p>BUILD ROOM UNAVAILABLE</p><h1>The build state could not be loaded.</h1><button onClick={reset}>Try again</button></main>;
}
