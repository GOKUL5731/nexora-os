# Jarvis Pet 3D Model

The floating Windows pet automatically uses an exported 3D model when one of these files exists:

- `nexora_os/assets/pet_model.glb`
- `nexora_os/assets/pet_model.gltf`
- `models/pet_model.glb`
- `models/pet_model.gltf`

You can also launch with a custom path:

```cmd
python -m nexora_os.pet_app --model C:\path\to\pet_model.glb
```

The current Meshy source models are:

- https://www.meshy.ai/s/XeMdqG
- https://www.meshy.ai/s/ATvJqY

Export/download the preferred Meshy model as GLB or GLTF and save it as `nexora_os/assets/pet_model.glb`. The one-click launcher will then show that animated 3D pet automatically. If no exported model exists, Jarvis falls back to `jarvis_robot_pet.png`.
