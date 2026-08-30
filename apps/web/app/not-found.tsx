import Link from "next/link";

export default function NotFound() {
  return <main className="error-screen"><p>404 / NO BUILD</p><h1>This prototype does not exist.</h1><Link href="/">Start a new build</Link></main>;
}
