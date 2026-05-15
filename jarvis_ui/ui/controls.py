def get_js_controls():
    return """
    let controls;
    function setupControls(camera, domElement) {
        controls = new THREE.OrbitControls(camera, domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.maxDistance = 2000;
        controls.minDistance = 300;
        
        // Restrict rotation slightly for a fixed tactical console feel
        controls.minAzimuthAngle = -Math.PI / 3;
        controls.maxAzimuthAngle = Math.PI / 3;
        controls.minPolarAngle = Math.PI / 3;
        controls.maxPolarAngle = Math.PI / 1.5;
        
        // Disable panning to keep it centered
        controls.enablePan = false;
    }
    """
