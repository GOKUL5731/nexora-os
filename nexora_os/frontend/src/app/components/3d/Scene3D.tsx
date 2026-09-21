import React, { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { CognitiveCore3D } from "./CognitiveCore3D";
import { NeuralNetwork } from "./NeuralNetwork";
import { useNexora } from "../../../context/NexoraContext";

interface Scene3DProps {
  children?: React.ReactNode;
}

export function Scene3D({ children }: Scene3DProps) {
  const { lowPowerMode, reducedMotion, gCoreState } = useNexora();
  const effectsDisabled = lowPowerMode || reducedMotion;

  if (lowPowerMode) {
    return (
      <div className="g2-spatial-fallback" aria-hidden="true">
        <div className={`g2-static-core state-${gCoreState.toLowerCase()}`} />
      </div>
    );
  }

  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true">
      <Canvas
        shadows={!effectsDisabled}
        gl={{
          antialias: !effectsDisabled,
          alpha: true,
          powerPreference: effectsDisabled ? "low-power" : "high-performance",
        }}
        dpr={effectsDisabled ? 1 : [1, 2]}
        frameloop={effectsDisabled ? "demand" : "always"}
      >
        <PerspectiveCamera makeDefault position={[0, 0, 15]} fov={50} />

        <ambientLight intensity={0.3} />
        <pointLight position={[10, 10, 10]} intensity={effectsDisabled ? 0.55 : 1} color="#00ffff" />
        {!effectsDisabled && <pointLight position={[-10, -10, -10]} intensity={0.5} color="#0066ff" />}

        {!effectsDisabled && <Environment preset="city" />}

        <Suspense fallback={null}>
          <CognitiveCore3D />
          {!effectsDisabled && <NeuralNetwork />}
        </Suspense>

        {!effectsDisabled && (
          <ContactShadows
            position={[0, -5, 0]}
            opacity={0.3}
            scale={20}
            blur={2}
            far={10}
            resolution={256}
            color="#00ffff"
          />
        )}

        <OrbitControls
          enableDamping={!effectsDisabled}
          dampingFactor={0.05}
          minDistance={5}
          maxDistance={30}
          maxPolarAngle={Math.PI / 1.5}
          minPolarAngle={Math.PI / 3}
        />

        {children}
      </Canvas>
    </div>
  );
}
