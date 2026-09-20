import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Mesh, SphereGeometry } from 'three';
import { useNexora } from '../../../context/NexoraContext';
import * as THREE from 'three';

export function CognitiveCore3D() {
  const meshRef = useRef<Mesh>(null);
  const innerCoreRef = useRef<Mesh>(null);
  const ringRef = useRef<Mesh>(null);

  const { voiceState, brainState, connected, busy } = useNexora();

  const speaking = voiceState === 'speaking';
  const listening = voiceState === 'listening' || busy;
  const currentStage = brainState?.stage ?? 'IDLE';
  const isActive = currentStage !== 'IDLE' && currentStage !== 'COMPLETE' && currentStage !== 'FAILED';

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
      const breathe = Math.sin(time * 0.5) * 0.1;
      const activeScale = isActive ? 1.2 : 1;
      meshRef.current.scale.setScalar(activeScale + breathe);
      meshRef.current.rotation.y = time * 0.1;
      meshRef.current.rotation.x = Math.sin(time * 0.2) * 0.1;
    }

    // Inner core pulsing
    if (innerCoreRef.current) {
      const pulse = speaking ? Math.sin(time * 8) * 0.3 : Math.sin(time * 2) * 0.1;
      innerCoreRef.current.scale.setScalar(0.8 + pulse);

      // Color based on state
      const hue = speaking ? 0.5 : listening ? 0.3 : isActive ? 0.1 : 0.55;
      innerCoreRef.current.material.color.setHSL(hue, 0.8, 0.5);
    }

    // Ring rotation
    if (ringRef.current) {
      ringRef.current.rotation.z = time * 0.2;
      ringRef.current.rotation.x = Math.sin(time * 0.3) * 0.2;
      const ringScale = speaking ? 1.5 : listening ? 1.3 : 1;
      ringRef.current.scale.setScalar(ringScale);
    }
  });

  return (
    <group>
      {/* Outer glow sphere */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[2, 32, 32]} />
        <meshBasicMaterial
          color={0x00ffff}
          transparent
          opacity={0.1}
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
          color={0x00ffff}
          transparent
          opacity={0.5}
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