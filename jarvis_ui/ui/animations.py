def get_js_animations():
    return """
    // Tween.js handles smooth easing for audio reactivity
    // See window.updateAudioLevel in scene3d HTML script
    
    // Typing effect for console
    function addConsoleLine(text) {
        const consoleOut = document.getElementById('console-output');
        const lines = consoleOut.innerHTML.split('<br>');
        if (lines.length > 5) {
            lines.shift();
        }
        lines.push('> ' + text);
        consoleOut.innerHTML = lines.join('<br>');
    }
    
    // Simulate some system activity
    setInterval(() => {
        const msgs = [
            "SCANNING LOCAL NETWORK...",
            "OPTIMIZING MEMORY ALLOCATION...",
            "ANALYZING SECURITY PROTOCOLS...",
            "SYNCING WITH OLLAMA ENGINE...",
            "BACKGROUND TASKS COMPLETED."
        ];
        if (Math.random() > 0.7) {
            const msg = msgs[Math.floor(Math.random() * msgs.length)];
            addConsoleLine(msg);
        }
    }, 4000);
    """
