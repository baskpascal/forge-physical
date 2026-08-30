"use client";

import { Canvas } from "@react-three/fiber";
import { Environment, Float, OrbitControls, RoundedBox } from "@react-three/drei";

function Enclosure() {
  return (
    <Float speed={1.1} rotationIntensity={0.1} floatIntensity={0.25}>
      <group rotation={[-0.18, -0.52, 0.03]}>
        <RoundedBox args={[3.9, 0.45, 2.8]} radius={0.16} smoothness={4} position={[0, -0.45, 0]}>
          <meshStandardMaterial color="#d9d7d0" roughness={0.38} metalness={0.08} />
        </RoundedBox>
        <RoundedBox args={[3.8, 0.16, 2.7]} radius={0.13} smoothness={4} position={[0, 0.13, 0]}>
          <meshStandardMaterial color="#f3f1ea" roughness={0.3} />
        </RoundedBox>
        <mesh position={[-0.75, 0.24, -0.1]} rotation={[Math.PI / 2, 0, 0]}>
          <planeGeometry args={[1.55, 0.88]} />
          <meshStandardMaterial color="#071412" roughness={0.2} />
        </mesh>
        <mesh position={[1.05, 0.27, 0]}>
          <cylinderGeometry args={[0.34, 0.34, 0.36, 48]} />
          <meshStandardMaterial color="#353a37" metalness={0.5} roughness={0.28} />
        </mesh>
      </group>
    </Float>
  );
}

export function EnclosureView() {
  return (
    <Canvas camera={{ position: [5.2, 4.2, 5.5], fov: 35 }} dpr={[1, 1.5]}>
      <color attach="background" args={["#ecebe6"]} />
      <ambientLight intensity={1.4} />
      <directionalLight position={[3, 6, 4]} intensity={2.3} />
      <Enclosure />
      <Environment preset="studio" />
      <OrbitControls enablePan={false} minDistance={5} maxDistance={9} autoRotate autoRotateSpeed={0.45} />
    </Canvas>
  );
}
