# Setup & Configuration Guide

This document explains how to properly configure Nexus for local development and avoid common path/environment issues.

## Quick Start (5 minutes)

### 1. Clone & Install
```bash
git clone https://github.com/abhi-dev99/burplefolk.git
cd burplefolk
python -m venv .venv
.venv\Scripts\activate  # On macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies
```bash
cd nexus-ui
npm install
cd ..
```

### 3. Start Services
```bash
# Terminal 1: Streamlit (recommended for quick start)
streamlit run app.py

# OR: Full Stack (Terminal 1, 2, 3)
# Terminal 1: Backend API
python api.py

# Terminal 2: React UI
cd nexus-ui && npm run dev

# Terminal 3: Streamlit
streamlit run app.py
```

## Configuration

### Environment Variables (Recommended)

All secrets and configuration should be set via **environment variables**. They take precedence over secrets files.

#### Python Backend (.env or export)
```bash
# Ollama (Local LLM)
export OLLAMA_ENDPOINT=http://localhost:11434
export OLLAMA_API_KEY=         # Leave empty if no auth

# Firebase (Agent login) - Optional
export FIREBASE_API_KEY=xxxxx
export FIREBASE_AUTH_DOMAIN=xxxxx.firebaseapp.com
export FIREBASE_PROJECT_ID=xxxxx
export FIREBASE_STORAGE_BUCKET=xxxxx.appspot.com
export AGENT_DEFAULT_EMAIL=user@example.com
```

#### React Frontend (.env.local)
```bash
# Create nexus-ui/.env.local from nexus-ui/.env.example
VITE_API_BASE=http://localhost:8000/api

# For remote servers:
# VITE_API_BASE=http://192.168.x.x:8000/api
```

### Secrets Files (Alternative)

If you prefer TOML files over environment variables:

#### `.streamlit/secrets.toml` (for Streamlit)
```bash
# Copy from .streamlit/secrets.toml.example
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Edit and fill in your values
# NOTE: This file is in .gitignore - never commit it
```

**Note**: Environment variables always take precedence over `.streamlit/secrets.toml`.

## Common Path Issues & Solutions

### Issue 1: "No secrets found" error when starting Streamlit

**Symptom:**
```
streamlit.errors.StreamlitSecretNotFoundError: No secrets found.
Valid paths for a secrets.toml file or secret directories are:
  C:\Users\..\.streamlit\secrets.toml
  C:\Users\...\burplefolk\.streamlit\secrets.toml
```

**Solution:**
The app is trying to read secrets. Choose one:

```bash
# Option A: Copy example secrets file (easiest)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Option B: Use environment variables instead (recommended)
export OLLAMA_ENDPOINT=http://localhost:11434
streamlit run app.py

# Option C: Create empty secrets file
mkdir -p .streamlit
echo "# Empty secrets" > .streamlit/secrets.toml
```

### Issue 2: React UI can't reach backend API (localhost:8000)

**Symptom:**
```
Error: Failed to analyze. Ensure backend API is running at localhost:8000!
```

**Solution:**

1. **Check backend is running:**
   ```bash
   # Terminal 1
   python api.py
   # Should show: "Uvicorn running on http://0.0.0.0:8000"
   ```

2. **Update React API endpoint if server is on different IP:**
   ```bash
   # Create nexus-ui/.env.local
   VITE_API_BASE=http://192.168.x.x:8000/api
   
   # Or set inline:
   cd nexus-ui
   VITE_API_BASE=http://192.168.1.100:8000/api npm run dev
   ```

3. **Check CORS is enabled:** Backend (api.py) has CORS enabled for `*`.

### Issue 3: npm dependencies not installed

**Symptom:**
```
Module not found: react, framer-motion, etc.
```

**Solution:**
```bash
cd nexus-ui
npm install
npm run dev
```

### Issue 4: Python package import errors

**Symptom:**
```
ModuleNotFoundError: No module named 'streamlit'
```

**Solution:**
```bash
# Make sure you're in the virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Try reinstalling requirements
pip install -r requirements.txt --force-reinstall
```

## Working Directory Requirements

**All commands must be run from the project root** (`cd burplefolk`):

```
✅ CORRECT:  cd burplefolk && streamlit run app.py
❌ WRONG:    cd burplefolk/nexus && streamlit run app.py
```

Relative paths depend on being at the project root:
- `.streamlit/secrets.toml`
- `outputs/`
- `nexus/` (Python modules)
- `nexus-ui/` (React app)

## Port Usage

**Default ports:**
- Streamlit: `http://localhost:8501`
- React UI: `http://localhost:5173`
- Backend API: `http://localhost:8000`

If ports are already in use, you can change them:

```bash
# Custom Streamlit port
streamlit run app.py --server.port 8502

# Custom React port
cd nexus-ui && npm run dev -- --port 5174

# Backend API uses FastAPI/Uvicorn (configured in api.py)
```

## Git & Secrets Safety

**IMPORTANT**: Never commit secrets!

Protected files (in `.gitignore`):
- `.streamlit/secrets.toml` ✅
- `.env`
- `.env.local` (frontend)
- `nexus-ui/.env` ✅
- `.venv/` ✅
- Various cache/build directories

Before committing:
```bash
git status  # Should NOT show secrets files

# If you accidentally staged them:
git rm --cached .streamlit/secrets.toml .env
git commit --amend
```

## Troubleshooting Checklist

- [ ] Virtual environment activated (`.venv\Scripts\activate`)
- [ ] Running from project root directory (`cd burplefolk`)
- [ ] `pip install -r requirements.txt` completed
- [ ] `cd nexus-ui && npm install` completed
- [ ] Environment variables set OR `secrets.toml` created
- [ ] Backend API running (if using React UI): `python api.py`
- [ ] Check ports aren't already in use: 8501, 5173, 8000
- [ ] Firewall not blocking localhost connections
- [ ] Running on same machine? Use `localhost` or `127.0.0.1`
- [ ] Running on network? Use actual IP address: `192.168.x.x`

## Multi-Machine Setup

### Serving on Network

**Backend:**
```bash
# No changes needed, FastAPI listens on 0.0.0.0
python api.py
```

**React UI:**
```bash
cd nexus-ui
npm run dev -- --host 0.0.0.0 --port 5173

# Update .env.local to point to actual server IP
VITE_API_BASE=http://192.168.1.100:8000/api
```

**Streamlit:**
```bash
streamlit run app.py --server.headless true --server.port 8501
# Access from another machine: http://server-ip:8501
```

## Optional: Local LLM (Ollama)

For AI-powered features without cloud dependencies:

```bash
# Install Ollama from https://ollama.ai

# Download a model
ollama pull llama2  # or llama3.1, neural-chat, etc.

# Keep Ollama running in background
ollama serve

# In your app, endpoint stays as: http://localhost:11434
```

## Getting Help

If issues persist:

1. Check `.venv/` is activated in terminal
2. Check you're in the project root directory
3. Run fresh install: `pip install -r requirements.txt --upgrade`
4. Check logs: `streamlit run app.py --logger.level=debug`
5. Check Python version: `python --version` (should be 3.10+)
6. Check Node version: `node --version` (should be 16+)

## Key Files Reference

```
burplefolk/
├── app.py                    # Streamlit main app
├── api.py                    # FastAPI backend server
├── requirements.txt          # Python dependencies
├── .streamlit/
│   ├── secrets.toml         # (Generated, in .gitignore)
│   └── secrets.toml.example # Template
├── nexus-ui/
│   ├── package.json         # React dependencies
│   ├── .env.example         # Frontend config template
│   ├── .env.local          # (Generated, in .gitignore)
│   └── src/App.tsx         # Main React component
├── nexus/                    # Python modules
│   ├── analysis.py
│   ├── ai.py
│   ├── agent_email.py
│   └── ...
└── .gitignore               # Excludes secrets and build files
```

---

**Last Updated:** March 27, 2026
