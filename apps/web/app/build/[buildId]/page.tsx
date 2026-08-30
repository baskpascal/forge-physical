import { BuildRoom } from "@/components/build-room";

export default async function BuildPage({ params }: { params: Promise<{ buildId: string }> }) {
  const { buildId } = await params;
  return <BuildRoom buildId={buildId} />;
}
