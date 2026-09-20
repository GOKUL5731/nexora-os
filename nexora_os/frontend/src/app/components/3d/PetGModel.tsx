import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";
import * as THREE from "three";

type PetGModelProps = {
  mood?: "idle" | "focus" | "happy";
};

function Antenna({ side }: { side: -1 | 1 }) {
  return (
    <group position={[side * 0.72, 1.18, 0]} rotation={[0, 0, side * -0.35]}>
      <mesh castShadow position={[0, 0.28, 0]}>
        <cylinderGeometry args={[0.035, 0.05, 0.62, 14]} />
        <meshStandardMaterial color="#7dd3fc" metalness={0.55} roughness={0.28} />
      </mesh>
      <mesh castShadow position={[0, 0.65, 0]}>
        <sphereGeometry args={[0.13, 24, 24]} />
        <meshStandardMaterial color="#f59e0b" emissive="#92400e" emissiveIntensity={0.55} roughness={0.25} />
      </mesh>
    </group>
  );
}

function Eye({ x, happy }: { x: number; happy: boolean }) {
  return (
    <group position={[x, 0.22, 0.62]}>
      <mesh castShadow scale={[1, happy ? 0.62 : 1, 1]}>
        <sphereGeometry args={[0.16, 32, 32]} />
        <meshStandardMaterial color="#e0f2fe" emissive="#38bdf8" emissiveIntensity={0.3} roughness={0.18} />
      </mesh>
      <mesh position={[0.04, 0.02, 0.12]} scale={[1, happy ? 0.72 : 1, 1]}>
        <sphereGeometry args={[0.07, 24, 24]} />
        <meshStandardMaterial color="#0f172a" roughness={0.2} />
      </mesh>
    </group>
  );
}

export function PetGModel({ mood = "idle" }: PetGModelProps) {
  const body = useRef<THREE.Group>(null);
  const leftArm = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Group>(null);
  const particles = useMemo(() => {
    return Array.from({ length: 18 }, (_, index) => ({
      angle: (index / 18) * Math.PI * 2,
      radius: 1.58 + (index % 4) * 0.08,
      y: -0.2 + (index % 6) * 0.13,
    }));
  }, []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (body.current) {
      body.current.position.y = Math.sin(t * 1.4) * 0.08;
      body.current.rotation.y = Math.sin(t * 0.6) * 0.18;
      body.current.rotation.z = Math.sin(t * 0.85) * 0.035;
    }
    if (leftArm.current) leftArm.current.rotation.z = 0.32 + Math.sin(t * 2.4) * 0.18;
    if (rightArm.current) rightArm.current.rotation.z = -0.32 + Math.cos(t * 2.1) * 0.18;
  });

  const happy = mood === "happy";
  const focus = mood === "focus";

  return (
    <group ref={body} position={[0, 0, 0]}>
      <group position={[0, 0.35, 0]}>
        <mesh castShadow receiveShadow>
          <capsuleGeometry args={[0.72, 0.92, 18, 36]} />
          <meshStandardMaterial color="#f8fafc" metalness={0.18} roughness={0.38} />
        </mesh>
        <mesh position={[0, 0.15, 0.08]} scale={[0.78, 0.58, 0.08]}>
          <sphereGeometry args={[0.55, 32, 32]} />
          <meshStandardMaterial color="#0f172a" metalness={0.3} roughness={0.24} />
        </mesh>
        <Eye x={-0.26} happy={happy} />
        <Eye x={0.26} happy={happy} />
        <Text
          position={[0, -0.38, 0.68]}
          fontSize={0.34}
          anchorX="center"
          anchorY="middle"
          color={focus ? "#f59e0b" : "#38bdf8"}
        >
          G
        </Text>
        <Antenna side={-1} />
        <Antenna side={1} />
      </group>

      <group ref={leftArm} position={[-0.82, 0.2, 0]}>
        <mesh castShadow rotation={[0.2, 0.1, 0.75]}>
          <capsuleGeometry args={[0.13, 0.56, 12, 18]} />
          <meshStandardMaterial color="#bae6fd" metalness={0.2} roughness={0.34} />
        </mesh>
      </group>
      <group ref={rightArm} position={[0.82, 0.2, 0]}>
        <mesh castShadow rotation={[0.1, -0.1, -0.75]}>
          <capsuleGeometry args={[0.13, 0.56, 12, 18]} />
          <meshStandardMaterial color="#bae6fd" metalness={0.2} roughness={0.34} />
        </mesh>
      </group>

      <mesh castShadow position={[-0.32, -0.78, 0.08]} rotation={[0.1, 0, 0.16]}>
        <capsuleGeometry args={[0.15, 0.42, 12, 18]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.15} roughness={0.42} />
      </mesh>
      <mesh castShadow position={[0.32, -0.78, 0.08]} rotation={[0.1, 0, -0.16]}>
        <capsuleGeometry args={[0.15, 0.42, 12, 18]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.15} roughness={0.42} />
      </mesh>

      {particles.map((particle, index) => (
        <mesh
          key={index}
          position={[
            Math.cos(particle.angle) * particle.radius,
            particle.y,
            Math.sin(particle.angle) * particle.radius,
          ]}
        >
          <boxGeometry args={[0.045, 0.045, 0.045]} />
          <meshStandardMaterial color={index % 3 === 0 ? "#f59e0b" : "#38bdf8"} emissive="#0369a1" emissiveIntensity={0.28} />
        </mesh>
      ))}
    </group>
  );
}
