def get_panels_html():
    return """
    <div id="panel-left" class="hologram-panel" style="width: 320px; height: 400px; display: none;">
        <div class="panel-header">SYSTEM METRICS</div>
        <div class="panel-content">
            <div class="metric-row">
                <span>CPU UTILIZATION</span>
                <span id="cpu-val" class="metric-value">0%</span>
            </div>
            <div class="progress-bar"><div id="cpu-bar" class="progress-fill"></div></div>
            <br>
            <div class="metric-row">
                <span>MEMORY ALLOCATION</span>
                <span id="ram-val" class="metric-value">0%</span>
            </div>
            <div class="progress-bar"><div id="ram-bar" class="progress-fill"></div></div>
            <br>
            <div class="metric-row">
                <span>STORAGE ARRAY</span>
                <span id="disk-val" class="metric-value">0%</span>
            </div>
            <div class="progress-bar"><div id="disk-bar" class="progress-fill"></div></div>
            <br>
            <div class="metric-row" style="margin-top: 20px;">
                <span>GPU ACCELERATION</span>
                <span class="metric-value" style="color: #0f0;">ONLINE</span>
            </div>
        </div>
    </div>

    <div id="panel-right" class="hologram-panel" style="width: 320px; height: 400px; display: none;">
        <div class="panel-header">AI CORE STATUS</div>
        <div class="panel-content">
            <div class="status-indicator" style="font-size: 18px; margin-bottom: 20px;">
                <span class="dot pulse-dot"></span> <span style="letter-spacing: 2px;">NEURAL LINK ACTIVE</span>
            </div>
            
            <div class="metric-row">
                <span>ROUTING LOGIC</span>
                <span class="metric-value">OLLAMA LOCAL</span>
            </div>
            <div class="metric-row">
                <span>LATENCY</span>
                <span class="metric-value">12ms</span>
            </div>
            <div class="metric-row">
                <span>VOICE MODULE</span>
                <span class="metric-value" style="color: #0f0;">LISTENING</span>
            </div>
            <div class="metric-row">
                <span>VISION MODULE</span>
                <span class="metric-value" style="color: #fa0;">STANDBY</span>
            </div>
            
            <div style="margin-top: 30px; border-top: 1px dashed rgba(0, 255, 255, 0.3); padding-top: 10px;">
                <span style="font-size: 10px; color: rgba(0, 255, 255, 0.6);">AUDIO REACTIVE SUBSYSTEM</span>
                <div class="progress-bar" style="height: 4px; background: rgba(0,255,255,0.05);"><div id="audio-bar" class="progress-fill" style="box-shadow: 0 0 5px #0ff; width: 0%;"></div></div>
            </div>
        </div>
    </div>

    <div id="panel-bottom" class="hologram-panel" style="width: 700px; height: 160px; display: none;">
        <div class="panel-header">COMMAND CONSOLE</div>
        <div class="panel-content" id="console-output" style="font-family: 'Courier New', monospace; color: #0ff; font-size: 13px; height: 100px; overflow: hidden; text-shadow: 0 0 4px #0ff;">
            > INITIATING PRIMARY BOOT SEQUENCE...<br>
            > CONNECTING TO LOCAL OLLAMA INSTANCE... OK<br>
            > ALLOCATING GPU MEMORY... OK<br>
            > SYSTEM ONLINE. AWAITING COMMANDS.
        </div>
    </div>
    
    <div id="panel-top" class="hologram-panel" style="width: 800px; height: 90px; text-align: center; display: none; background: transparent; border: none; box-shadow: none;">
        <div style="font-size: 42px; font-weight: bold; letter-spacing: 15px; margin-top: 10px; text-shadow: 0 0 15px #0ff; color: #fff;">J.A.R.V.I.S.</div>
        <div style="font-size: 14px; letter-spacing: 8px; color: #0ff; text-shadow: 0 0 5px #0ff;">TACTICAL INTERFACE v3.0</div>
    </div>
    """

def get_panels_css():
    return """
    body {
        margin: 0; 
        overflow: hidden; 
        background-color: #000;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        user-select: none;
    }
    .hologram-panel {
        background: rgba(0, 15, 30, 0.45);
        border: 1px solid rgba(0, 255, 255, 0.3);
        box-shadow: 0 0 20px rgba(0, 255, 255, 0.15), inset 0 0 30px rgba(0, 255, 255, 0.1);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        color: #0ff;
        padding: 25px;
        box-sizing: border-box;
        border-radius: 4px;
        transition: all 0.3s ease;
        position: absolute;
    }
    .hologram-panel:hover {
        box-shadow: 0 0 40px rgba(0, 255, 255, 0.4), inset 0 0 40px rgba(0, 255, 255, 0.2);
        border: 1px solid rgba(0, 255, 255, 0.8);
        background: rgba(0, 20, 40, 0.6);
    }
    .panel-header {
        font-size: 16px;
        font-weight: bold;
        border-bottom: 2px solid rgba(0, 255, 255, 0.4);
        padding-bottom: 12px;
        margin-bottom: 20px;
        letter-spacing: 3px;
        text-shadow: 0 0 8px #0ff;
        color: #fff;
    }
    .panel-content {
        font-size: 13px;
        line-height: 1.6;
        letter-spacing: 1px;
    }
    .metric-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 5px;
    }
    .metric-value {
        font-weight: bold;
        text-shadow: 0 0 5px #0ff;
    }
    .progress-bar {
        width: 100%;
        height: 4px;
        background: rgba(0, 255, 255, 0.1);
        margin-bottom: 15px;
        overflow: hidden;
    }
    .progress-fill {
        height: 100%;
        background: #0ff;
        width: 0%;
        box-shadow: 0 0 10px #0ff;
        transition: width 0.3s ease;
    }
    .dot {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #0f0;
        box-shadow: 0 0 15px #0f0;
        margin-right: 8px;
        vertical-align: middle;
    }
    .pulse-dot {
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.7); }
        70% { transform: scale(1.1); box-shadow: 0 0 0 15px rgba(0, 255, 0, 0); }
        100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }
    }
    """
