# Jarvis — Phase 1 Foundation + LLM

This implements Phase 1A–1D from the project plan:
- project skeleton
- Qwen3.5/Ollama integration
- tool/function calling
- Windows tools
- background hotkey toggle
- Windows startup launcher

## Prerequisites

1. Windows 10/11
2. Python 3.10+
3. Ollama installed and running
4. Qwen3.5 4B available in Ollama

## Setup

```powershell
cd Jarvis
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` if you want custom settings. The current code reads
environment variables directly; a future phase can add a proper config loader.

Pull the model:

```powershell
ollama pull qwen3.5:4b
```

Run:

```powershell
python main.py
```

## Phase 1 interaction

Type:

```text
What time is it?
Open Chrome.
Open https://google.com
```

Toggle Jarvis:

```text
Ctrl + Alt + J
```

## Model swap

The LLM is isolated behind `jarvis/core/llm.py`. To switch later:

```powershell
$env:JARVIS_LLM_MODEL="qwen3:4b"
python main.py
```

No agent/tool architecture changes should be necessary.

## Important

The current startup implementation launches the Python process through a Startup
`.cmd` file. We will replace this with a proper packaged/background launcher
during the polish phase.
