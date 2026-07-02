# NEXORA OS

This is the consolidated NEXORA platform. The official Command Center UI is the only frontend, and all backend modules live under `nexora_os/backend`.

## Structure

```text
nexora_os/
├── frontend/
├── backend/
│   ├── core/
│   ├── agents/
│   ├── workflows/
│   ├── memory/
│   ├── voice/
│   ├── vision/
│   ├── automation/
│   ├── ai_lab/
│   ├── api/
│   └── monitoring/
├── plugins/
├── models/
├── databases/
├── logs/
├── tests/
└── docs/
```

## Run

Double-click from Windows Explorer to run as a Windows desktop application:

```text
NEXORA_ONE_CLICK.cmd
```

That launcher starts Ollama when available, detects the local Ollama model, prepares frontend/backend dependencies, starts the backend locally, and opens NEXORA in a native desktop window. It does not open an external browser. If Ollama has no local model, it offers to download `llama3.2:1b`.

To build a packaged Windows app folder, run:

```text
BUILD_WINDOWS_EXE.cmd
```

Manual run:

```powershell
cd C:\Users\gokul\Downloads\nexora_v3_complete
python -m nexora_os.backend.api.app --serve-ui --port 7474
```

Open `http://127.0.0.1:7474`.

## Development

```powershell
cd nexora_os\frontend
npm install
npm run build
```

The API exposes live data over REST and `/ws/events`; the React UI consumes that backend directly. Generated agents are validated, written to the AI Lab sandbox, and registered, but generated code is never executed directly.
