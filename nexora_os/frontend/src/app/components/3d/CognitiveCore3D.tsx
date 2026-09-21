import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Mesh } from 'three';
import { useNexora } from '../../../context/NexoraContext';
import * as THREE from 'three';

const CORE_COLORS: Record<string, { hue: number; emissive: number; scale: number; ring: number }> = {
  OFFLINE: { hue: 0.0, emissive: 0.12, scale: 0.82, ring: 0.62 },
  STARTING: { hue: 0.12, emissive: 0.45, scale: 1.02, ring: 0.9 },
  IDLE: { hue: 0.55, emissive: 0.42, scale: 1, ring: 1 },
  LISTENING: { hue: 0.48, emissive: 0.72, scale: 1.16, ring: 1.35 },
  UNDERSTANDING: { hue: 0.52, emissive: 0.65, scale: 1.1, ring: 1.22 },
  THINKING: { hue: 0.62, emissive: 0.76, scale: 1.18, ring: 1.28 },
  PLANNING: { hue: 0.72, emissive: 0.7, scale: 1.14, ring: 1.32 },
  EXECUTING: { hue: 0.1, emissive: 0.82, scale: 1.24, ring: 1.42 },
  OBSERVING: { hue: 0.28, emissive: 0.64, scale: 1.08, ring: 1.18 },
  VERIFYING: { hue: 0.38, emissive: 0.72, scale: 1.12, ring: 1.26 },
  SPEAKING: { hue: 0.5, emissive: 0.9, scale: 1.18, ring: 1.5 },
  LEARNING: { hue: 0.42, emissive: 0.74, scale: 1.2, ring: 1.36 },
  VISION: { hue: 0.16, emissive: 0.8, scale: 1.15, ring: 1.38 },
  ERROR: { hue: 0.0, emissive: 0.9, scale: 1.1, ring: 1.18 },
  SUCCESS: { hue: 0.34, emissive: 0.78, scale: 1.14, ring: 1.24 },
};

export function CognitiveCore3D() {
  const meshRef = useRef<Mesh>(null);
  const innerCoreRef = useRef<Mesh>(null);
  const ringRef = useRef<Mesh>(null);

  const { gCoreState } = useNexora();
  const visual = CORE_COLORS[gCoreState] ?? CORE_COLORS.IDLE;
  const isActive = !["IDLE", "OFFLINE"].includes(gCoreState);
  const speaking = gCoreState === "SPEAKING";
  const listening = gCoreState === "LISTENING";

  // Create neural layers geometry
  const neuralLayers = useMemo(() => {
    const layers = [];
    for (let i = 0; i < 5; i++) {
      const geometry = new THREE.IcosahedronGeometry(1.5 + i * 0.3, 1);
      const material = new THREE.MeshBasicMaterial({
        color: 0x00ffff,
        wireframe: true,
        transparent: true,
        opacity: 0.15 - i * 0.02,
      });
      layers.push({ geometry, material, speed: 0.001 + i * 0.0005 });
    }
    return layers;
  }, []);

  useFrame((state) => {
    const time = state.clock.getElapsedTime();

    // Main core breathing animation
    if (meshRef.current) {
      const breathe = Math.sin(time * (isActive ? 0.9 : 0.45)) * 0.08;
      meshRef.current.scale.setScalar(visual.scale + breathe);
      meshRef.current.rotation.y = time * (gCoreState === "EXECUTING" ? 0.22 : 0.1);
      meshRef.current.rotation.x = Math.sin(time * 0.2) * 0.1;
    }

    // Inner core pulsing
    if (innerCoreRef.current) {
      const pulse = speaking ? Math.sin(time * 8) * 0.3 : Math.sin(time * (isActive ? 3 : 1.7)) * 0.1;
      innerCoreRef.current.scale.setScalar(0.8 + pulse);

      const material = innerCoreRef.current.material as THREE.MeshStandardMaterial;
      material.color.setHSL(visual.hue, 0.82, gCoreState === "OFFLINE" ? 0.28 : 0.5);
      material.emissive.setHSL(visual.hue, 0.9, gCoreState === "OFFLINE" ? 0.18 : 0.42);
      material.emissiveIntensity = visual.emissive;
    }

    // Ring rotation
    if (ringRef.current) {
      ringRef.current.rotation.z = time * (gCoreState === "VERIFYING" ? 0.5 : 0.2);
      ringRef.current.rotation.x = Math.sin(time * 0.3) * 0.2;
      ringRef.current.scale.setScalar(visual.ring);
    }
  });

  return (
    <group>
      {/* Outer glow sphere */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[2, 32, 32]} />
        <meshBasicMaterial
          color={gCoreState === "ERROR" ? 0xff3b3b : gCoreState === "OFFLINE" ? 0x66707a : 0x00ffff}
          transparent
          opacity={gCoreState === "OFFLINE" ? 0.045 : 0.1}
          wireframe
        />
      </mesh>

      {/* Inner solid core */}
      <mesh ref={innerCoreRef}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshStandardMaterial
          color={0x00ffff}
          emissive={0x00ffff}
          emissiveIntensity={0.5}
          metalness={0.8}
          roughness={0.2}
        />
      </mesh>

      {/* Rotating rings */}
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.5, 0.05, 16, 100]} />
        <meshBasicMaterial
          color={gCoreState === "ERROR" ? 0xff5b4f : gCoreState === "SUCCESS" ? 0x4dff9a : 0x00ffff}
          transparent
          opacity={gCoreState === "OFFLINE" ? 0.22 : listening ? 0.72 : 0.5}
        />
      </mesh>

      {/* Neural layers */}
      {neuralLayers.map((layer, i) => (
        <mesh key={i} geometry={layer.geometry} material={layer.material} />
      ))}

      {/* Memory particles - visible when memory retrieval occurs */}
      {isActive && (
        <group>
          {Array.from({ length: 20 }).map((_, i) => (
            <mesh key={i} position={[
              Math.cos(i * 0.5) * 3,
              Math.sin(i * 0.5) * 3,
              Math.cos(i * 0.3) * 3
            ]}>
              <sphereGeometry args={[0.05, 8, 8]} />
              <meshBasicMaterial color={0x00ffff} transparent opacity={0.6} />
            </mesh>
          ))}
        </group>
      )}
    </group>
  );
}
