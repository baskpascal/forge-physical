export function artifactUrl(buildId: string, storedPath?: string): string | null {
  if (!storedPath || storedPath.includes("\\")) return null;
  const parts = storedPath.split("/");
  if (parts[0] === buildId) parts.shift();
  if (parts.length === 0 || parts.some((part) => !part || part === "." || part === "..")) return null;
  if (parts[0] !== "hardware") return null;

  const base = process.env.NEXT_PUBLIC_BUILD_API_URL ?? "http://127.0.0.1:8080";
  const encodedPath = parts.map(encodeURIComponent).join("/");
  return `${base.replace(/\/$/, "")}/api/builds/${encodeURIComponent(buildId)}/artifacts/${encodedPath}`;
}
