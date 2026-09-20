import React from 'react';
import { EffectComposer, Bloom } from '@react-three/postprocessing';

export function PostProcessingEffects() {
  return (
    <EffectComposer>
      <Bloom
        luminanceThreshold={0.2}
        luminanceSmoothing={0.9}
        height={300}
        intensity={1.5}
        radius={0.8}
      />
    </EffectComposer>
  );
}