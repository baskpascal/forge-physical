"use client";

import { Environment, OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useEffect, useMemo, useState } from "react";
import { BufferGeometry } from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { normalizeStlParts } from "@/lib/stl-geometry";

type PartState =
  | { status: "loading" }
  | { status: "missing" }
  | { status: "parse_error" }
  | { status: "ready"; geometry: BufferGeometry };

const LOADING: PartState = { status: "loading" };
const MISSING: PartState = { status: "missing" };

async function loadStl(url: string, signal: AbortSignal): Promise<PartState> {
  try {
    const response = await fetch(url, { cache: "no-store", signal });
    if (response.status === 404) return { status: "missing" };
    if (!response.ok) return { status: "parse_error" };
    const geometry = new STLLoader().parse(await response.arrayBuffer());
    if (!geometry.getAttribute("position") || geometry.getAttribute("position").count === 0) {
      geometry.dispose();
      return { status: "parse_error" };
    }
    return { status: "ready", geometry };
  } catch (error) {
    if (signal.aborted) throw error;
    return { status: "parse_error" };
  }
}

function useStl(url?: string | null): PartState {
  const [loaded, setLoaded] = useState<{ url: string; part: PartState } | null>(null);
  const state = loaded && loaded.url === url
    ? loaded.part
    : url
      ? LOADING
      : MISSING;

  useEffect(() => {
    const controller = new AbortController();
    if (!url) return () => controller.abort();
    void loadStl(url, controller.signal).then((next) => {
      if (!controller.signal.aborted) setLoaded({ url, part: next });
    }).catch(() => undefined);
    return () => controller.abort();
  }, [url]);

  useEffect(() => () => {
    if (loaded?.part.status === "ready") loaded.part.geometry.dispose();
  }, [loaded]);
  return state;
}

function Enclosure({ base, lid }: { base: PartState; lid: PartState }) {
  const geometries = useMemo(() => {
    const source = [base, lid].filter(
      (part): part is Extract<PartState, { status: "ready" }> => part.status === "ready",
    );
    return normalizeStlParts(source.map((part) => part.geometry));
  }, [base, lid]);
  useEffect(() => () => geometries.forEach((geometry) => geometry.dispose()), [geometries]);

  return (
    <group rotation={[-Math.PI / 2, 0, -0.32]}>
      {geometries.map((geometry, index) => (
        <mesh geometry={geometry} key={index} position={[0, 0, index * 0.55]}>
          <meshStandardMaterial
            color={index === 0 ? "#d9d7d0" : "#f3f1ea"}
            roughness={0.34}
            metalness={0.05}
          />
        </mesh>
      ))}
    </group>
  );
}

function statusLabel(base: PartState, lid: PartState): string | null {
  const states = [base.status, lid.status];
  if (states.includes("loading")) return "LOADING ENCLOSURE MESHES";
  if (states.includes("parse_error")) return "STL PARSE ERROR";
  if (states.includes("missing")) return "ENCLOSURE ARTIFACT MISSING";
  return null;
}

export function EnclosureView({ baseUrl, lidUrl }: { baseUrl?: string | null; lidUrl?: string | null }) {
  const base = useStl(baseUrl);
  const lid = useStl(lidUrl);
  const label = statusLabel(base, lid);
  return (
    <>
      <Canvas camera={{ position: [5.2, 4.2, 5.5], fov: 35 }} dpr={[1, 1.5]}>
        <color attach="background" args={["#ecebe6"]} />
        <ambientLight intensity={1.4} />
        <directionalLight position={[3, 6, 4]} intensity={2.3} />
        <Enclosure base={base} lid={lid} />
        <Environment preset="studio" />
        <OrbitControls enablePan={false} minDistance={5} maxDistance={9} autoRotate autoRotateSpeed={0.45} />
      </Canvas>
      {label && <div className={`mesh-status ${label.includes("ERROR") ? "error" : ""}`} role="status">{label}</div>}
    </>
  );
}
