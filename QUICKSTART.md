# 🚀 Quick Start with .bat Files

For non-technical users, use these Windows batch files to set up and run Advise Workbench in seconds!

## Files Included

### 1. `INSTALL_ALL.bat` — Complete Setup (Run First!)
**What it does:**
- ✅ Downloads and installs Python 3.12 (if needed)
- ✅ Downloads and installs Node.js v20 LTS (if needed)
- ✅ Creates Python virtual environment
- ✅ Installs all backend packages
- ✅ Installs all frontend packages
- ✅ Sets up `.env` configuration
- ✅ Optionally starts the app

**How to use:**
1. Double-click `INSTALL_ALL.bat`
2. Wait 5-15 minutes for completion (downloads are large)
3. When prompted, add your Anthropic API key to `.env`
4. Choose to start the app or exit

**⏱️ Time needed:** 10-20 minutes (first time only)

---

### 2. `START_APP.bat` — Launch the Application (Run Every Time)
**What it does:**
- ✅ Activates Python virtual environment
- ✅ Checks ports 3000 and 8000 (uses alternatives if needed)
- ✅ Starts backend API server
- ✅ Starts frontend web application
- ✅ Displays URLs to access

**How to use:**
1. After running `INSTALL_ALL.bat`, double-click `START_APP.bat` any time you want to start the app
2. Wait 30-60 seconds for both services to start
3. Open **http://localhost:3000** in your browser
4. Two Windows console windows will open (Backend and Frontend) — **leave them running**
5. To stop the app, close both console windows

**⏱️ Time needed:** 1 minute

---

## Step-by-Step for Complete Beginners

### First Time Setup (Requires API Key)

**Step 1: Get API Key** (5 minutes)
1. Go to: https://console.anthropic.com
2. Sign up or log in with your account
3. Create API key
4. Copy the key (starts with `sk-ant-`)

**Step 2: Run Setup** (15 minutes)
1. Double-click `INSTALL_ALL.bat`
2. Let it run (may download ~500MB of files)
3. When done, a Notepad window opens with `.env` file
4. Find the line: `ANTHROPIC_API_KEY=your_api_key_here`
5. Replace with your key: `ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE`
6. Save and close
7. Choose to start the app

**Step 3: Use the App** (Now!)
1. Browser opens to http://localhost:3000
2. Sign up with any email and password
3. Start creating projects!

---

### Every Time You Want to Use the App

**Just double-click:** `START_APP.bat`

That's it! 🎉

---

## Troubleshooting

### "Python not found" or "Node.js not found"
- **Solution:** Restart your computer and run `INSTALL_ALL.bat` again

### "Port 8000 already in use"
- **Solution:** The script automatically uses port 8001 instead
- Access at: http://127.0.0.1:8001

### "Port 3000 already in use"
- **Solution:** The script automatically uses port 3001 instead
- Access at: http://localhost:3001

### "ANTHROPIC_API_KEY is not set"
- **Solution:** 
  1. Open `.env` file in Notepad
  2. Find `ANTHROPIC_API_KEY=your_api_key_here`
  3. Replace with your actual key
  4. Save
  5. Run `START_APP.bat` again

### Backend shows "Application startup failed"
- **Solution:**
  1. Close both console windows
  2. Open `.env` and verify `ANTHROPIC_API_KEY` is set correctly
  3. Run `START_APP.bat` again

### "Connection refused" when opening browser
- **Solution:** Wait 30 seconds and try again. Services take time to start.

### Slow installation or download errors
- **Solution:** Check your internet connection. Some downloads are large (~500MB)

---

## Alternative: Free API (No API Key Needed)

If you don't want to use an Anthropic API key:

**Step 1: Install Claude Code CLI** (One time)
```
npm install -g @anthropic-ai/claude-code
claude
# Sign in when prompted
```

**Step 2: Edit `.env`** (One time)
- Open `.env` in Notepad
- Find line with: `ANTHROPIC_API_KEY=...`
- Add new line: `LLM_PROVIDER=claude_cli`
- Save

**Step 3: Use the app normally**
- Run `START_APP.bat` as usual

---

## What Files Can You Generate?

Once the app is running, you can create:

- 📊 **Executive Presentations** (.pptx) — decks with slides, layouts, images
- 📄 **Word Documents** (.docx) — reports, SOPs, guides
- 📊 **Excel Spreadsheets** (.xlsx) — matrices, data tables, analysis
- 📋 **Process Maps** — flowcharts and diagrams
- 📈 **Analytics Reports** — dashboards and summaries

All files are saved to: `workspace/` folder on your computer.

---

## File Locations

```
Your Repo Folder/
├── INSTALL_ALL.bat          ← Run this first
├── START_APP.bat            ← Run this every time
├── SETUP_COMPLETE.md        ← Read this for help
├── WINDOWS_SETUP.md         ← Read this for troubleshooting
├── README_RUN.md            ← Full usage guide
├── .env                      ← Your configuration (edit with Notepad)
├── .venv/                    ← Python environment (created automatically)
├── frontend/                 ← Web app code
├── src/                      ← Backend code
└── workspace/                ← Your projects and files
```

---

## System Requirements

- **Windows 10 or newer** (Windows 11 recommended)
- **4GB RAM minimum** (8GB recommended)
- **2GB disk space** for installation
- **Internet connection** for downloading packages and API calls
- **Administrator rights** (for first-time setup only)

---

## Getting Help

1. **Read the guides:**
   - `SETUP_COMPLETE.md` — General setup guide
   - `WINDOWS_SETUP.md` — Windows-specific help
   - `README_RUN.md` — How to use the application

2. **Check console output:**
   - When running the app, watch the console windows for error messages
   - Copy/paste errors for debugging

3. **Verify your API key:**
   - https://console.anthropic.com — Check your API key is valid

---

## One-Liner Quick Start

If everything is installed, you can just run:
```
START_APP.bat
```

Then open: **http://localhost:3000**

---

**Happy Building! 🚀**
