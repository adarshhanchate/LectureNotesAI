# 📚 LectureNotes AI — Lecture-to-Study-Book Converter

Turn lecture videos (YouTube link or uploaded file) into structured, studio-quality study books in PDF — complete with organized notes, clean vector math formulas, numerical problem cards, and a difficulty-tiered question bank with an answer key.

---

## 🪟 Windows Setup (Primary Platform)

> **Tuned for:** Windows 10/11, 16 GB RAM, Intel Iris iGPU (No CUDA required).

### Option A: One-Click Quick Start (Recommended)
Double-click or run from command prompt:
```bat
start.bat
```
`start.bat` will automatically:
1. Create a Python virtual environment in `.venv\` if missing.
2. Install all required dependencies from `requirements.txt`.
3. Create your `.env` configuration file from `.env.example`.
4. Run the hardware and tool diagnostic (`backend.check_system`).
5. Open your default web browser to `http://localhost:8000`.
6. Start the FastAPI backend server.

---

### Option B: Manual Windows Step-by-Step Setup

#### 1. Install Prerequisites
Open PowerShell or Command Prompt:

- **Python 3.10+**: Ensure Python is added to your Windows PATH.
- **FFmpeg** (Required for audio extraction):
  ```powershell
  winget install Gyan.FFmpeg
  ```
- **WeasyPrint / PDF Runtime**:
  - The app includes a portable standalone WeasyPrint binary in `bin/weasyprint/` that runs out-of-the-box on Windows!
  - *Optional (for native Python WeasyPrint)*:
    1. Install MSYS2 from https://www.msys2.org/
    2. In MSYS2 terminal run: `pacman -S mingw-w64-x86_64-pango`
    3. Add `C:\msys64\mingw64\bin` to PATH or set `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin`
  - *Fallback*: Headless Chrome / Edge (`chrome --headless --print-to-pdf`).
- **Ollama (For 100% Offline Local AI)**:
  ```powershell
  winget install Ollama.Ollama
  ollama serve
  ollama pull qwen2.5:3b    # Fast mode (Recommended for 16GB RAM)
  ollama pull qwen2.5:7b    # Standard model (High accuracy)
  ```

#### 2. Virtual Environment & Dependencies
```bat
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
```

#### 3. Configure `.env`
Copy `.env.example` to `.env`:
```bat
copy .env.example .env
```
Key settings in `.env`:
```ini
LLM_PROVIDER=gemini          # 'gemini' (cloud free tier) or 'ollama' (local offline)
GEMINI_API_KEY=AIzaSy...     # Your free Google Gemini API key
GEMINI_MODEL=                # Run 'python -m backend.llm.check' to discover models for your key
OLLAMA_MODEL=qwen2.5:7b      # Standard model
OLLAMA_FAST_MODEL=qwen2.5:3b # Fast mode model
DEMO_MODE=false              # true = watermarked demo content; false = require active AI provider
```

#### 4. Run System Diagnostics
```bat
python -m backend.check_system
python -m backend.llm.check
```

#### 5. Start the Server
```bat
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Open **http://localhost:8000** in your browser.

---

## 🐧 Linux & macOS Setup (Secondary)

```bash
chmod +x start.sh
./start.sh
```

**System Packages:**
- Ubuntu / Debian: `sudo apt update && sudo apt install ffmpeg libpango-1.0-0 libharfbuzz0b`
- macOS: `brew install ffmpeg pango`

---

## ⚙️ Low-End Hardware Tuning (16 GB RAM + Intel Iris)

This application is strictly optimized for laptops without dedicated NVIDIA GPUs:
1. **faster-whisper CPU int8**: Transcribes speech in ~1.5 GB RAM without CUDA; VAD skips silent pauses.
2. **Sequential Memory Isolation**: Immediately after transcription finishes, Whisper is deleted and garbage collected (`del model; gc.collect()`) before the LLM runs. Whisper and the LLM **never** occupy RAM simultaneously.
3. **Compound Transcript Caching**: Caches STT by `SHA-256(file) + model + language` in `.cache/transcripts/`, saving 3-5 minutes on repeat runs.
4. **Ollama Fast Mode**: Defaults to `qwen2.5:3b` with `num_ctx=4096` and `temperature=0.2` for speedy CPU inference.
5. **Clean Math Rendering**: Uses `matplotlib.mathtext` to convert math directly to SVG with zero external Node/KaTeX dependencies and graceful Unicode fallback.
6. **Graceful Subprocess Cancellation**: Terminating or cancelling a job kills the entire process tree on Windows (`taskkill /F /T /PID` or `psutil`), preventing orphaned ffmpeg/yt-dlp tasks.

---

## 🛠️ Diagnostic & Testing CLI Tools

| Command | Purpose |
| :--- | :--- |
| `python -m backend.check_system` | Verifies RAM, CPU cores, FFmpeg, yt-dlp, WeasyPrint/GTK, and Ollama status. |
| `python -m backend.llm.check` | Tests LLM connection, queries available Gemini models for your key, or tests Ollama ping. |
| `python -m backend.pdf.preview` | Compiles `sample_book.pdf` instantly using `templates/sample_lecture.json` without running STT/LLM. |

---

## 📄 License & Terms
For personal and educational use only. Please respect video copyright and platform terms of service.
