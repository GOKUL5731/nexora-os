import React, { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { PetGModel } from "./PetGModel";

export function PetGStage({ mood = "idle" }: { mood?: "idle" | "focus" | "happy" }) {
  return (
    <div className="pet-stage" aria-label="Interactive 3D Pet G companion">
      <Canvas shadows dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
        <PerspectiveCamera makeDefault position={[0, 0.8, 5.2]} fov={42} />
        <ambientLight intensity={0.62} />
        <directionalLight position={[4, 5, 6]} intensity={1.35} castShadow />
        <pointLight position={[-3, 2, 4]} intensity={1.1} color="#38bdf8" />
        <pointLight position={[3, -1, 2]} intensity={0.62} color="#f59e0b" />
        <Suspense fallback={null}>
          <PetGModel mood={mood} />
          <Environment preset="studio" />
        </Suspense>
        <ContactShadows position={[0, -1.18, 0]} opacity={0.3} scale={6} blur={2.4} far={4} />
        <OrbitControls enablePan={false} enableDamping dampingFactor={0.08} minDistance={3.5} maxDistance={7} />
      </Canvas>
    </div>
  );
}
