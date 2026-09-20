import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Points, Line } from '@react-three/drei';
import { useNexora } from '../../../context/NexoraContext';
import * as THREE from 'three';

interface NodeData {
  position: THREE.Vector3;
  velocity: THREE.Vector3;
  type: 'memory' | 'agent' | 'workflow' | 'connector' | 'llm' | 'tool' | 'vision' | 'voice' | 'execution';
  active: boolean;
}

export function NeuralNetwork() {
  const nodesRef = useRef<THREE.Points>(null);
  const linesRef = useRef<THREE.LineSegments>(null);

  const { agents, workflows, brainState, events } = useNexora();

  // Generate neural nodes
  const nodes = useMemo(() => {
    const nodeData: NodeData[] = [];
    const types: NodeData['type'][] = ['memory', 'agent', 'workflow', 'connector', 'llm', 'tool', 'vision', 'voice', 'execution'];

    // Create nodes in a spherical distribution
    for (let i = 0; i < 200; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const radius = 4 + Math.random() * 4;

      const position = new THREE.Vector3(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.sin(phi) * Math.sin(theta),
        radius * Math.cos(phi)
      );

      const velocity = new THREE.Vector3(
        (Math.random() - 0.5) * 0.01,
        (Math.random() - 0.5) * 0.01,
        (Math.random() - 0.5) * 0.01
      );

      nodeData.push({
        position,
        velocity,
        type: types[Math.floor(Math.random() * types.length)],
        active: false
      });
    }

    return nodeData;
  }, []);

  // Activate nodes based on backend state
  const activeNodes = useMemo(() => {
    const activeSet = new Set<number>();

    // Activate agent nodes
    agents.runtime.forEach((agent, idx) => {
      if (agent.status === 'running') {
        activeSet.add(idx % 200);
      }
    });

    // Activate workflow nodes
    workflows.forEach((workflow, idx) => {
      if (workflow.enabled) {
        activeSet.add((idx + 50) % 200);
      }
    });

    // Activate based on recent events
    events.slice(-10).forEach((event, idx) => {
      if (event.topic.includes('memory')) {
        activeSet.add((idx + 100) % 200);
      } else if (event.topic.includes('voice')) {
        activeSet.add((idx + 120) % 200);
      } else if (event.topic.includes('vision')) {
        activeSet.add((idx + 140) % 200);
      }
    });

    return activeSet;
  }, [agents, workflows, events]);

  // Create connection lines
  const connections = useMemo(() => {
    const linePositions: number[] = [];
    const connectionDistance = 2.5;

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const distance = nodes[i].position.distanceTo(nodes[j].position);
        if (distance < connectionDistance) {
          linePositions.push(
            nodes[i].position.x, nodes[i].position.y, nodes[i].position.z,
            nodes[j].position.x, nodes[j].position.y, nodes[j].position.z
          );
        }
      }
    }

    return new Float32Array(linePositions);
  }, [nodes]);

  // Node colors based on type and activity
  const colors = useMemo(() => {
    const colorArray = new Float32Array(nodes.length * 3);
    const typeColors: Record<NodeData['type'], [number, number, number]> = {
      memory: [0, 0.5, 1],      // Blue
      agent: [1, 0.5, 0],      // Orange
      workflow: [0, 1, 0.5],    // Green
      connector: [0.5, 0, 1],   // Purple
      llm: [1, 0, 0.5],        // Pink
      tool: [0.5, 1, 0],       // Lime
      vision: [1, 1, 0],        // Yellow
      voice: [0, 1, 1],        // Cyan
      execution: [1, 0, 0]      // Red
    };

    nodes.forEach((node, i) => {
      const isActive = activeNodes.has(i);
      const baseColor = typeColors[node.type];
      const intensity = isActive ? 1 : 0.3;

      colorArray[i * 3] = baseColor[0] * intensity;
      colorArray[i * 3 + 1] = baseColor[1] * intensity;
      colorArray[i * 3 + 2] = baseColor[2] * intensity;
    });

    return colorArray;
  }, [nodes, activeNodes]);

  // Create position array
  const positions = useMemo(() => {
    return new Float32Array(nodes.flatMap(n => [n.position.x, n.position.y, n.position.z]));
  }, [nodes]);

  useFrame((state) => {
    const time = state.clock.getElapsedTime();

    // Update node positions
    nodes.forEach((node, i) => {
      node.position.add(node.velocity);

      // Boundary check - keep nodes in sphere
      if (node.position.length() > 8) {
        node.velocity.multiplyScalar(-1);
      }

      // Gentle orbit around center
      const orbitSpeed = 0.001;
      const x = node.position.x;
      const z = node.position.z;
      node.position.x = x * Math.cos(orbitSpeed) - z * Math.sin(orbitSpeed);
      node.position.z = x * Math.sin(orbitSpeed) + z * Math.cos(orbitSpeed);
    });

    // Update point positions
    if (nodesRef.current) {
      const positions = nodesRef.current.geometry.attributes.position.array as Float32Array;
      nodes.forEach((node, i) => {
        positions[i * 3] = node.position.x;
        positions[i * 3 + 1] = node.position.y;
        positions[i * 3 + 2] = node.position.z;
      });
      nodesRef.current.geometry.attributes.position.needsUpdate = true;
    }

    // Update line connections periodically
    if (linesRef.current && Math.floor(time * 10) % 5 === 0) {
      const linePositions: number[] = [];
      const connectionDistance = 2.5;

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const distance = nodes[i].position.distanceTo(nodes[j].position);
          if (distance < connectionDistance) {
            linePositions.push(
              nodes[i].position.x, nodes[i].position.y, nodes[i].position.z,
              nodes[j].position.x, nodes[j].position.y, nodes[j].position.z
            );
          }
        }
      }

      const lineGeometry = new THREE.BufferGeometry();
      lineGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linePositions), 3));
      linesRef.current.geometry.dispose();
      linesRef.current.geometry = lineGeometry;
    }
  });

  return (
    <group>
      {/* Neural nodes */}
      <Points ref={nodesRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={nodes.length}
            array={positions}
            itemSize={3}
          />
          <bufferAttribute
            attach="attributes-color"
            count={nodes.length}
            array={colors}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.08}
          vertexColors
          transparent
          opacity={0.8}
          sizeAttenuation
        />
      </Points>

      {/* Neural connections */}
      <lineSegments ref={linesRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={connections.length / 3}
            array={connections}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial
          color={0x00ffff}
          transparent
          opacity={0.15}
          linewidth={1}
        />
      </lineSegments>
    </group>
  );
}