import os
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QTimer, QUrl

from core.system_monitor import SystemMonitor
from ui.audio_visualizer import AudioVisualizerThread
from ui.panels import get_panels_html, get_panels_css
from ui.animations import get_js_animations
from ui.controls import get_js_controls

class JARVISScene3D:
    def __init__(self, parent_window):
        self.widget = QWidget(parent_window)
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.webview = QWebEngineView()
        # Enable WebGL
        self.webview.settings().setAttribute(self.webview.settings().WebAttribute.WebGLEnabled, True)
        self.webview.settings().setAttribute(self.webview.settings().WebAttribute.LocalContentCanAccessRemoteUrls, True)
        layout.addWidget(self.webview)
        
        self.monitor = SystemMonitor()
        
        # Start Audio Visualizer
        self.audio_thread = AudioVisualizerThread()
        self.audio_thread.audio_level_signal.connect(self.on_audio_level)
        self.audio_thread.start()
        
        # Setup Timer for stats update
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1500)  # 1.5 second intervals
        
        self.load_scene()

    def get_widget(self):
        return self.widget
        
    def load_scene(self):
        html_content = self.generate_html()
        
        html_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'scene.html')
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        self.webview.setUrl(QUrl.fromLocalFile(os.path.abspath(html_path)))

    def generate_html(self):
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>JARVIS 3D Interface</title>
            <style>
                {get_panels_css()}
                #webgl-container {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; pointer-events: none; }}
                #css-container {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 2; pointer-events: none; }}
                .hologram-panel {{ pointer-events: auto; }}
            </style>
            <!-- Three.js from unpkg for stability -->
            <script src="https://unpkg.com/three@0.128.0/build/three.min.js"></script>
            <script src="https://unpkg.com/three@0.128.0/examples/js/renderers/CSS3DRenderer.js"></script>
            <script src="https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
            
            <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/EffectComposer.js"></script>
            <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/RenderPass.js"></script>
            <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/ShaderPass.js"></script>
            <script src="https://unpkg.com/three@0.128.0/examples/js/shaders/CopyShader.js"></script>
            <script src="https://unpkg.com/three@0.128.0/examples/js/shaders/LuminosityHighPassShader.js"></script>
            <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/UnrealBloomPass.js"></script>
            
            <script src="https://cdnjs.cloudflare.com/ajax/libs/tween.js/18.6.4/tween.umd.js"></script>
        </head>
        <body>
            <div id="webgl-container"></div>
            
            <!-- Hidden DOM elements to be converted to CSS3D objects -->
            <div style="display: none;">
                {get_panels_html()}
            </div>

            <script>
                {get_js_animations()}
                {get_js_controls()}
                
                // MAIN SCENE SETUP
                let scene, camera, renderer, cssRenderer, composer;
                let coreGroup, outerRing, innerRing, particles;
                let audioLevel = 0.0;
                
                init();
                animate();
                
                function init() {{
                    scene = new THREE.Scene();
                    scene.fog = new THREE.FogExp2(0x000000, 0.0005);
                    
                    camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 3000);
                    camera.position.set(0, 0, 1200);
                    
                    // WebGL Renderer
                    renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
                    renderer.setSize(window.innerWidth, window.innerHeight);
                    renderer.setPixelRatio(window.devicePixelRatio);
                    renderer.toneMapping = THREE.ReinhardToneMapping;
                    renderer.setClearColor(0x000000, 1);
                    document.getElementById('webgl-container').appendChild(renderer.domElement);
                    
                    // CSS3D Renderer
                    cssRenderer = new THREE.CSS3DRenderer();
                    cssRenderer.setSize(window.innerWidth, window.innerHeight);
                    cssRenderer.domElement.id = 'css-container';
                    document.body.appendChild(cssRenderer.domElement);
                    
                    // OrbitControls attach to cssRenderer domElement so interactions work
                    setupControls(camera, cssRenderer.domElement);
                    
                    buildCore();
                    buildPanels();
                    
                    // Bloom Setup
                    const renderScene = new THREE.RenderPass(scene, camera);
                    const bloomPass = new THREE.UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.5, 0.4, 0.85);
                    bloomPass.threshold = 0.1;
                    bloomPass.strength = 1.8;
                    bloomPass.radius = 0.8;
                    
                    composer = new THREE.EffectComposer(renderer);
                    composer.addPass(renderScene);
                    composer.addPass(bloomPass);
                    
                    window.addEventListener('resize', onWindowResize);
                }}
                
                function buildCore() {{
                    coreGroup = new THREE.Group();
                    scene.add(coreGroup);
                    
                    // Glowing sphere center
                    const sphereGeo = new THREE.IcosahedronGeometry(70, 2);
                    const sphereMat = new THREE.MeshBasicMaterial({{ 
                        color: 0x00ffff, 
                        wireframe: true,
                        transparent: true,
                        opacity: 0.8
                    }});
                    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
                    coreGroup.add(sphere);
                    
                    // Solid inner core
                    const innerGeo = new THREE.SphereGeometry(40, 32, 32);
                    const innerMat = new THREE.MeshBasicMaterial({{ color: 0x00aaff }});
                    const innerSphere = new THREE.Mesh(innerGeo, innerMat);
                    coreGroup.add(innerSphere);
                    
                    // Outer rings
                    const ringGeo1 = new THREE.TorusGeometry(140, 1.5, 16, 100);
                    const ringMat1 = new THREE.MeshBasicMaterial({{ color: 0x00aaff }});
                    outerRing = new THREE.Mesh(ringGeo1, ringMat1);
                    outerRing.rotation.x = Math.PI / 2;
                    coreGroup.add(outerRing);
                    
                    const ringGeo2 = new THREE.TorusGeometry(100, 1, 16, 100);
                    const ringMat2 = new THREE.MeshBasicMaterial({{ color: 0x0055ff }});
                    innerRing = new THREE.Mesh(ringGeo2, ringMat2);
                    innerRing.rotation.y = Math.PI / 2;
                    coreGroup.add(innerRing);
                    
                    // Surrounding Particles
                    const partGeo = new THREE.BufferGeometry();
                    const partCount = 1500;
                    const posArray = new Float32Array(partCount * 3);
                    for(let i=0; i<partCount*3; i++) {{
                        posArray[i] = (Math.random() - 0.5) * 800;
                    }}
                    partGeo.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
                    const partMat = new THREE.PointsMaterial({{ size: 2, color: 0x00ffff, transparent: true, opacity: 0.5 }});
                    particles = new THREE.Points(partGeo, partMat);
                    coreGroup.add(particles);
                    
                    // Outer boundary grid sphere
                    const gridGeo = new THREE.SphereGeometry(600, 32, 32);
                    const gridMat = new THREE.MeshBasicMaterial({{ color: 0x002244, wireframe: true, transparent: true, opacity: 0.15 }});
                    const gridSphere = new THREE.Mesh(gridGeo, gridMat);
                    scene.add(gridSphere);
                }}
                
                function buildPanels() {{
                    const leftDom = document.getElementById('panel-left');
                    const rightDom = document.getElementById('panel-right');
                    const bottomDom = document.getElementById('panel-bottom');
                    const topDom = document.getElementById('panel-top');
                    
                    leftDom.style.display = 'block';
                    rightDom.style.display = 'block';
                    bottomDom.style.display = 'block';
                    topDom.style.display = 'block';
                    
                    const leftObj = new THREE.CSS3DObject(leftDom);
                    leftObj.position.set(-500, 0, 200);
                    leftObj.rotation.y = Math.PI / 5;
                    scene.add(leftObj);
                    
                    const rightObj = new THREE.CSS3DObject(rightDom);
                    rightObj.position.set(500, 0, 200);
                    rightObj.rotation.y = -Math.PI / 5;
                    scene.add(rightObj);
                    
                    const bottomObj = new THREE.CSS3DObject(bottomDom);
                    bottomObj.position.set(0, -320, 250);
                    bottomObj.rotation.x = -Math.PI / 6;
                    scene.add(bottomObj);
                    
                    const topObj = new THREE.CSS3DObject(topDom);
                    topObj.position.set(0, 350, 100);
                    scene.add(topObj);
                }}
                
                function onWindowResize() {{
                    camera.aspect = window.innerWidth / window.innerHeight;
                    camera.updateProjectionMatrix();
                    renderer.setSize(window.innerWidth, window.innerHeight);
                    cssRenderer.setSize(window.innerWidth, window.innerHeight);
                    composer.setSize(window.innerWidth, window.innerHeight);
                }}
                
                function animate() {{
                    requestAnimationFrame(animate);
                    TWEEN.update();
                    controls.update();
                    
                    // Core Animation
                    const targetScale = 1.0 + (audioLevel * 0.8);
                    
                    // Smooth scaling for the core
                    coreGroup.scale.x += (targetScale - coreGroup.scale.x) * 0.1;
                    coreGroup.scale.y += (targetScale - coreGroup.scale.y) * 0.1;
                    coreGroup.scale.z += (targetScale - coreGroup.scale.z) * 0.1;
                    
                    coreGroup.rotation.y += 0.005;
                    outerRing.rotation.x += 0.01;
                    outerRing.rotation.y += 0.005;
                    innerRing.rotation.x -= 0.01;
                    innerRing.rotation.z += 0.02;
                    
                    particles.rotation.y -= 0.001;
                    
                    composer.render();
                    cssRenderer.render(scene, camera);
                }}
                
                // Expose to Python
                window.updateStats = function(cpu, ram, disk) {{
                    document.getElementById('cpu-val').innerText = cpu.toFixed(1) + '%';
                    document.getElementById('cpu-bar').style.width = cpu + '%';
                    
                    document.getElementById('ram-val').innerText = ram.toFixed(1) + '%';
                    document.getElementById('ram-bar').style.width = ram + '%';
                    
                    document.getElementById('disk-val').innerText = disk.toFixed(1) + '%';
                    document.getElementById('disk-bar').style.width = disk + '%';
                }};
                
                window.updateAudioLevel = function(level) {{
                    // level is 0.0 to 1.0
                    new TWEEN.Tween({{l: audioLevel}})
                        .to({{l: level}}, 100)
                        .onUpdate(function(obj) {{ 
                            audioLevel = obj.l; 
                            document.getElementById('audio-bar').style.width = (audioLevel * 100) + '%';
                        }})
                        .start();
                }};
            </script>
        </body>
        </html>
        """
        return html

    def update_stats(self):
        stats = self.monitor.get_stats()
        js_code = f"window.updateStats({stats['cpu_percent']}, {stats['ram_percent']}, {stats['disk_percent']});"
        self.webview.page().runJavaScript(js_code)
        
    def on_audio_level(self, level):
        js_code = f"window.updateAudioLevel({level});"
        self.webview.page().runJavaScript(js_code)

    def cleanup(self):
        self.timer.stop()
        self.audio_thread.stop()
