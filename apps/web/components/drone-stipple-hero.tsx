"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { EffectComposer, Noise } from "@react-three/postprocessing";
import gsap from "gsap";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const vertexShader = /* glsl */ `
  uniform sampler2D uMap;
  uniform float uTime;
  uniform float uReveal;
  uniform vec2 uPointer;
  attribute vec2 aUv;
  varying float vInk;
  varying float vAlpha;
  void main() {
    vec4 source = texture2D(uMap, aUv);
    float ink = 1.0 - dot(source.rgb, vec3(0.299, 0.587, 0.114));
    float visible = smoothstep(0.06, 0.42, ink) * source.a;
    float boundary = smoothstep(0.08, 0.35, ink) * (1.0 - smoothstep(0.42, 0.88, ink));
    vec3 transformed = position;
    float localWave = sin(aUv.y * 22.0 + uTime * .43) + cos(aUv.x * 18.0 - uTime * .36);
    transformed.xy += vec2(localWave, sin(localWave + uTime * .22)) * .0032;
    transformed.xy += normalize(transformed.xy + .0001) * boundary * sin(uTime * .55 + aUv.x * 16.0) * .014;
    float pointerDistance = distance(transformed.xy, uPointer);
    transformed.xy += normalize(transformed.xy - uPointer + .0001) * smoothstep(.30, 0.0, pointerDistance) * .024;
    transformed.y += (1.0 - uReveal) * .17;
    vInk = ink;
    vAlpha = visible * uReveal;
    gl_PointSize = (1.45 + ink * 4.1 + sin(uTime * .7 + aUv.x * 12.0) * .25) * (1.0 + boundary * .12);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  varying float vInk;
  varying float vAlpha;
  void main() {
    float circle = 1.0 - smoothstep(.34, .5, distance(gl_PointCoord, vec2(.5)));
    if (circle < .01 || vAlpha < .02) discard;
    gl_FragColor = vec4(vec3(.045, .052, .047), circle * vAlpha * (.35 + vInk * .7));
  }
`;

function StipplePoints({ compact }: { compact: boolean }) {
  const material = useRef<THREE.ShaderMaterial>(null);
  const pointer = useRef(new THREE.Vector2(8, 8));
  const grid = compact ? [92, 56] : [156, 92];
  const geometry = useMemo(() => {
    const [columns, rows] = grid;
    const positions = new Float32Array(columns * rows * 3);
    const uvs = new Float32Array(columns * rows * 2);
    let index = 0;
    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < columns; column += 1) {
        const u = column / (columns - 1);
        const v = row / (rows - 1);
        positions[index * 3] = (u - .5) * 3.35;
        positions[index * 3 + 1] = (v - .5) * 2.05;
        positions[index * 3 + 2] = 0;
        uvs[index * 2] = u;
        uvs[index * 2 + 1] = v;
        index += 1;
      }
    }
    const result = new THREE.BufferGeometry();
    result.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    result.setAttribute("aUv", new THREE.BufferAttribute(uvs, 2));
    return result;
  }, [grid]);

  const uniforms = useMemo(() => ({
    uMap: { value: new THREE.TextureLoader().load("/drone-silhouette.png") },
    uTime: { value: 0 },
    uReveal: { value: 0 },
    uPointer: { value: pointer.current },
  }), []);

  useEffect(() => {
    const timeline = gsap.timeline();
    if (material.current) timeline.to(material.current.uniforms.uReveal, { value: 1, duration: 1.8, ease: "power2.out", delay: .1 });
    return () => { timeline.kill(); };
  }, []);

  useFrame((state) => {
    if (!material.current) return;
    material.current.uniforms.uTime.value = state.clock.elapsedTime;
    pointer.current.set(state.pointer.x * 1.55, state.pointer.y * .95);
  });

  return <points geometry={geometry}><shaderMaterial ref={material} uniforms={uniforms} vertexShader={vertexShader} fragmentShader={fragmentShader} transparent depthWrite={false} /></points>;
}

export default function DroneStippleHero() {
  const [reduced, setReduced] = useState(true);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return (
    <div className="drone-visual" aria-label="A living halftone illustration of a quadcopter drone">
      <div className="drone-fallback" aria-hidden="true"><img src="/drone-silhouette.png" alt="" /></div>
      {!reduced && <Canvas className="drone-canvas" dpr={[1, 1.5]} gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }} camera={{ position: [0, 0, 2.3], fov: 48 }}>
        <StipplePoints compact={typeof window !== "undefined" && window.innerWidth < 700} />
        <EffectComposer multisampling={0}><Noise opacity={.018} premultiply /></EffectComposer>
      </Canvas>}
      <p className="visual-caption">01 / AUTONOMOUS ASSEMBLY</p>
    </div>
  );
}
