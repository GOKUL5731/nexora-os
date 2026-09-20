import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment, ContactShadows } from '@react-three/drei';
import { CognitiveCore3D } from './CognitiveCore3D';
import { NeuralNetwork } from './NeuralNetwork';

interface Scene3DProps {
  children?: React.ReactNode;
}

export function Scene3D({ children }: Scene3DProps) {
  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true">
      <Canvas
        shadows
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance'
        }}
        dpr={[1, 2]}
      >
        <PerspectiveCamera makeDefault position={[0, 0, 15]} fov={50} />

        {/* Lighting */}
        <ambientLight intensity={0.3} />
        <pointLight position={[10, 10, 10]} intensity={1} color="#00ffff" />
        <pointLight position={[-10, -10, -10]} intensity={0.5} color="#0066ff" />

        {/* Environment */}
        <Environment preset="city" />

        {/* 3D Components */}
        <Suspense fallback={null}>
          <CognitiveCore3D />
          <NeuralNetwork />
        </Suspense>

        {/* Ground reflection */}
        <ContactShadows
          position={[0, -5, 0]}
          opacity={0.3}
          scale={20}
          blur={2}
          far={10}
          resolution={256}
          color="#00ffff"
        />

        {/* Camera Controls */}
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          minDistance={5}
          maxDistance={30}
          maxPolarAngle={Math.PI / 1.5}
          minPolarAngle={Math.PI / 3}
        />

        {/* Children for overlay content */}
        {children}
      </Canvas>
    </div>
  );
}
