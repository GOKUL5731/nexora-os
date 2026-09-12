# Jarvis Command Deck

The current Windows frontend now uses an original cinematic command-deck layout:
central runtime state, telemetry, task details, command entry, optional speech,
microphone action, subsystem navigation, and backend events. Existing specialist
pages remain available; their individual redesign and acceptance are unfinished.

Research reference: Perception's Iron Man 2 technology-design case study:
https://www.experienceperception.com/work/iron-man-2/
The case study describes design and animation of futuristic interface elements.
This implementation uses that visual direction, not fictional capability claims.

Verified: Vite production build; real Qt desktop window; live WebSocket-fed
CPU/RAM/GPU values and module/event state; automatic port fallback after Windows
rejected port 7474. The screenshot is locally available at logs/jarvis-redesign.png.
Build retains a large-bundle warning. No separate type checker is configured.
Background runtime responses now update the command deck response panel.

Windows: double-click run_project.cmd. It delegates to the existing dependency,
model and frontend preparation launcher and opens the native Qt application.
Linux/macOS: bash run_project.sh prepares a venv and starts Qt; this path has not
been executed on those operating systems. Install Ollama and a suitable model
separately there. The app can display unavailable model state without Ollama.

The project is not production-certified. Full microphone/camera acceptance,
permission hardening, all-page interaction testing and packaging remain open.
Existing uncommitted backend and frontend work predates this redesign; a release
must include and validate those dependencies before publishing to GitHub.
