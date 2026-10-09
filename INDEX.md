# 📋 INDEX - All Setup & Documentation Files

## 🎯 START HERE

### For Non-Technical Users (No Coding!)
1. **[README_FIRST.md](README_FIRST.md)** ← **Read this first!**
   - Complete overview of everything that's ready
   - Three-step quick start
   - Sharing instructions

2. **[INSTALL_ALL.bat](INSTALL_ALL.bat)** ← **Run to set up**
   - One-click complete installation
   - Handles Python, Node.js, packages, everything
   - Run once on first setup
   - Double-click to run

3. **[START_APP.bat](START_APP.bat)** ← **Run to start using**
   - One-click app launcher
   - Starts backend and frontend
   - Opens browser automatically
   - Run every time you want to use the app
   - Double-click to run

4. **[QUICKSTART.md](QUICKSTART.md)**
   - Quick reference guide
   - Troubleshooting for common issues
   - System requirements

---

## 📚 SETUP & CONFIGURATION GUIDES

### First-Time Setup (Follow These)
1. **[README_RUN.md](README_RUN.md)** (9.8 KB)
   - Updated with Windows winget installation
   - Step-by-step setup walkthrough
   - Detailed prerequisites
   - End-to-end example with sample project

2. **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)** (7.2 KB)
   - Complete Windows-specific guide
   - Installation via winget (recommended)
   - Troubleshooting section
   - Alternative install methods

3. **[SETUP_COMPLETE.md](SETUP_COMPLETE.md)** (4.9 KB)
   - What was installed
   - Three easy next steps
   - Quick commands reference
   - Documentation links

### For Developers
- **[docs/SETUP.md](docs/SETUP.md)** — Full technical setup
- **[docs/ARCHITECTURE.md](docs/02-architecture/ARCHITECTURE.md)** — System design
- **[docs/README.md](docs/README.md)** — Documentation index

---

## ⚙️ BATCH FILES FOR WINDOWS (Easy One-Click Setup!)

### [INSTALL_ALL.bat](INSTALL_ALL.bat) (9.2 KB)
**What it does:**
- Checks for Python 3.12 (downloads if missing)
- Checks for Node.js v20 LTS (downloads if missing)
- Creates Python virtual environment
- Installs all backend packages
- Installs all frontend packages
- Configures .env file
- Optionally starts the app

**How to use:**
```
Double-click INSTALL_ALL.bat
Wait 15-20 minutes
Answer any prompts
Add your API key when asked
```

**Run once** on first setup

---

### [START_APP.bat](START_APP.bat) (4.8 KB)
**What it does:**
- Activates Python virtual environment
- Checks ports (uses alternatives if needed)
- Starts backend API server
- Starts frontend web app
- Displays URLs to access

**How to use:**
```
Double-click START_APP.bat
Wait 30-60 seconds
Browser opens to http://localhost:3000
Leave both console windows running
```

**Run every time** you want to use the app

---

## 📄 DOCUMENTATION (Read These for Help)

| File | Size | Purpose |
|------|------|---------|
| **README_FIRST.md** | 6.8 KB | Overview & quick start |
| **QUICKSTART.md** | 5.7 KB | Non-technical quick reference |
| **README_RUN.md** | 9.8 KB | How to run the app |
| **WINDOWS_SETUP.md** | 7.2 KB | Windows installation guide |
| **SETUP_COMPLETE.md** | 4.9 KB | Setup walkthrough |
| **CLAUDE.md** | 2.9 KB | Project structure overview |

---

## 📁 FOLDER STRUCTURE

```
Advise Workbench/
│
├── 📋 INDEX.md                ← You are here!
├── 📋 README_FIRST.md         ← Start here (non-technical)
├── 📋 QUICKSTART.md           ← Quick reference
├── 📋 README_RUN.md           ← Full usage guide
├── 📋 WINDOWS_SETUP.md        ← Windows help
├── 📋 SETUP_COMPLETE.md       ← Setup details
│
├── 🔨 INSTALL_ALL.bat         ← Setup script (run once)
├── 🚀 START_APP.bat           ← Launch script (run always)
│
├── ⚙️  .env                    ← Configuration (add API key here)
├── ⚙️  .env.example           ← Configuration template
│
├── 🐍 .venv/                  ← Python environment
│
├── 🎨 frontend/               ← Web app (React/Next.js)
│   ├── package.json
│   ├── node_modules/          ← Frontend dependencies
│   └── src/
│
├── 🔧 src/                    ← Backend (FastAPI)
│   ├── app/
│   ├── core/
│   ├── memory/
│   └── ...
│
├── 📦 requirements.txt        ← Python dependencies
├── 📦 requirements-dev.txt    ← Python dev dependencies
│
├── 📁 data/examples/          ← Sample projects
│   └── northwind-p2p/         ← Try this first!
│
├── 📁 workspace/              ← Your projects & files (auto-created)
│
├── 📁 docs/                   ← Full documentation
│   ├── SETUP.md
│   ├── ARCHITECTURE.md
│   └── ...
│
├── 📁 tests/                  ← Test files
│
├── 📁 scripts/                ← Helper scripts
│   ├── run_agent.sh          ← Main start script (bash/Git Bash)
│   └── ...
│
├── Makefile                   ← Developer shortcuts
├── README.md                  ← Project overview
└── CLAUDE.md                  ← Development guidelines
```

---

## 🚀 QUICK START (3 STEPS)

### Step 1️⃣ — Setup (First Time Only - 20 Minutes)
```
1. Double-click: INSTALL_ALL.bat
2. Wait for completion
3. Add API key to .env when prompted
```

### Step 2️⃣ — Launch (Every Time - 1 Minute)
```
1. Double-click: START_APP.bat
2. Wait 30 seconds
3. Browser opens automatically
```

### Step 3️⃣ — Use (In Browser)
```
1. Sign up with any email & password
2. Create a project
3. Upload documents
4. Ask Sheldon (AI assistant) for what you need
5. Get generated PPTX, DOCX, XLSX files
```

---

## 🔑 Getting Your API Key

### Option A: Anthropic API (Recommended)
1. Visit: https://console.anthropic.com
2. Sign up or log in
3. Create API Key
4. Copy key (starts with `sk-ant-`)
5. Paste into `.env` file, line 135

### Option B: Claude Code CLI (Free, No Key)
```
npm install -g @anthropic-ai/claude-code
claude
```
Then add to `.env`: `LLM_PROVIDER=claude_cli`

---

## 🎯 WHAT YOU CAN DO

**Generate Professional Documents:**
- 📊 PowerPoint Presentations (.pptx)
- 📄 Word Documents (.docx)
- 📊 Excel Spreadsheets (.xlsx)
- 📈 Process Maps & Diagrams
- 📋 Analysis Reports

**Use AI to:**
- Analyze uploaded documents
- Summarize content
- Extract key insights
- Generate recommendations
- Create structured outputs

**All files save to:**
- `workspace/` folder on your computer
- Yours to keep forever!

---

## 🌐 AFTER STARTUP

Once **START_APP.bat** runs and shows "Ready":

| Purpose | URL |
|---------|-----|
| **Use the App** | http://localhost:3000 |
| **API Documentation** | http://127.0.0.1:8000/docs |
| **Backend Health** | http://127.0.0.1:8000/health |

---

## 📊 TRY THE SAMPLE PROJECT

**Northwind P2P Demo** (Full working example):

1. Create project: "Northwind P2P"
2. Download from: `data/examples/northwind-p2p/source-documents/`
   - `01_procure_to_pay_current_state.md`
   - `02_discovery_workshop_notes.txt`
   - `05_baseline_metrics_memo.md`
3. Upload all three files
4. Ask Sheldon: "Build an executive presentation on P2P transformation"
5. Type: "go"
6. **Output:** PPTX file in 10-20 minutes!

---

## ❓ NEED HELP?

### Most Common Issues

**"Python not found"**
- Restart your computer after running INSTALL_ALL.bat

**"Port 8000/3000 already in use"**
- START_APP.bat automatically uses alternative ports
- Check console output for actual URLs

**"API key not working"**
- Verify key format: starts with `sk-ant-`
- Check it's active at console.anthropic.com

**App won't start**
- Run INSTALL_ALL.bat again to repair
- Check `.env` has API key set

### Documentation References
- **README_FIRST.md** — Overview & setup
- **QUICKSTART.md** — Quick reference
- **WINDOWS_SETUP.md** — Windows troubleshooting
- **README_RUN.md** — Full usage guide

---

## 💾 SHARING WITH OTHERS

**To share the app with teammates:**

1. Copy entire folder to their computer
2. They run: `INSTALL_ALL.bat` (once)
3. They add their API key to `.env`
4. They run: `START_APP.bat` (every time)
5. They access: http://localhost:3000

**NO CODE CHANGES NEEDED!** ✅

---

## 📊 Installation Summary

| Component | Status | Version |
|-----------|--------|---------|
| Python | ✅ | 3.12.10 |
| Node.js | ✅ | v26.7.0+ |
| npm | ✅ | 11.19.0+ |
| Backend Packages | ✅ | Installed |
| Frontend Packages | ✅ | Installed |
| Virtual Environment | ✅ | .venv/ |
| Database | ✅ | Ready |
| Workspace | ✅ | Ready |
| Documentation | ✅ | Complete |

---

## ✅ YOU'RE READY!

Everything is installed and configured.

**Next Steps:**
1. Read: README_FIRST.md
2. Add: API key to .env
3. Run: START_APP.bat
4. Enjoy: http://localhost:3000

**Total time to first use: 25-30 minutes!** ⏱️

---

**Last Updated:** October 8, 2024
**Status:** ✅ Production Ready
**Platform:** Windows 10/11
