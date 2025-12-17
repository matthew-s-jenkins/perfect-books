# 🚀 How to Start Perfect Books

Perfect Books is a portable personal finance application with **no database server required**! It uses SQLite and runs locally on your computer.

---

## ✅ Quick Start (Windows)

### Option 1: One-Click Startup (Easiest)

1. **Navigate to the Perfect_Books folder:**
   ```
   c:\Projects\Perfect_Books
   ```

2. **Double-click:** `START_WINDOWS.bat`

3. **Your browser will automatically open** to the login page!

4. **What you'll see in the terminal:**
   ```
   ============================================================
   Perfect Books - Personal Finance Manager
   ============================================================

   [1/6] Checking Python version... [OK] Python 3.13.1
   [2/6] Checking dependencies... [OK]
   [3/6] Database found... [OK]
   [4/6] Backing up your data... [OK] Saved to Documents/PerfectBooks_Data
   [5/6] Checking for migrations... [OK] No pending migrations
   [6/6] Starting Perfect Books server...

   ============================================================
   Perfect Books is running!
   ============================================================

     Server: http://127.0.0.1:5001
     Press Ctrl+C to stop the server
   ```

5. **To stop the server:** Press `Ctrl+C` in the terminal window

### Option 2: Command Line (Manual)

1. **Open Command Prompt** (Win + R, type `cmd`, press Enter)

2. **Navigate to Perfect Books:**
   ```cmd
   cd c:\Projects\Perfect_Books
   ```

3. **Run the launcher:**
   ```cmd
   python start.py
   ```

4. **Open your browser** to:
   ```
   http://127.0.0.1:5001
   ```

---

## 🍎 Quick Start (Mac)

1. **Open Terminal** and navigate to Perfect_Books folder:
   ```bash
   cd /path/to/Perfect_Books
   ```

2. **Install dependencies** (first time only):
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Run the launcher:**
   - **Option A:** Double-click `START_MAC.command`
   - **Option B:** In Terminal: `python3 start.py`

4. **Browser opens automatically** to http://127.0.0.1:5001

---

## 🌐 What You Should See

### In the Terminal:
```
============================================================
Perfect Books - Personal Finance Manager
============================================================

[1/6] Checking Python version... [OK] Python 3.13.1
[2/6] Checking dependencies... [OK]
[3/6] Database found... [OK]
[4/6] Backing up your data... [OK] Saved to Documents/PerfectBooks_Data
[5/6] Checking for migrations... [OK] No pending migrations
[6/6] Starting Perfect Books server...

============================================================
Perfect Books is running!
============================================================

  Server: http://127.0.0.1:5001
  Press Ctrl+C to stop the server
```

### In the Browser:
- You should see the **Perfect Books login page**
- **First time?** Click "Register here" to create an account
- **Returning user?** Log in with your credentials

---

## 🎯 First Time Setup

When you run Perfect Books for the first time:

1. **Database is automatically created** at `src/data/perfectbooks.db`
2. **No configuration needed** - it just works!
3. **Register a new account** on the login page
4. **Set up your accounts** (checking, savings, credit cards, etc.)
5. **Start tracking your finances!**

---

## 🔧 Troubleshooting

### ❌ "Python is not installed or not in PATH"

**Fix:**
1. Install Python 3.8+ from https://www.python.org/downloads/
2. **Important:** Check "Add Python to PATH" during installation
3. Restart your terminal and try again

### ❌ "Missing required packages"

**Fix:**
```cmd
pip install -r requirements.txt
```

### ❌ Port 5001 is Already in Use

**Check what's using it:**
```cmd
netstat -ano | findstr :5001
```

**Fix:**
- Close the other application
- Or kill the process: `taskkill /PID <process_id> /F`
- Or change the port in `src/api.py` (search for `port=5001`)

### ❌ Browser Doesn't Open Automatically

**Fix:**
- Manually open your browser
- Go to: http://127.0.0.1:5001

### ❌ "An error occurred" Message

**Fix:**
- Open the terminal where the server is running
- Look for error messages in red
- Common issues:
  - Missing Python packages → Run `pip install -r requirements.txt`
  - Wrong Python version → Need Python 3.8 or higher
  - Database locked → Close other instances of Perfect Books

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `START_WINDOWS.bat` | Windows one-click launcher |
| `START_MAC.command` | Mac one-click launcher |
| `start.py` | Cross-platform Python launcher |
| `src/data/perfectbooks.db` | Your SQLite database (auto-created) |
| `src/api.py` | Flask API server |
| `src/engine.py` | Business logic |
| `index.html` | Main dashboard |
| `login.html` | Login page |

---

## 🗄️ Database Information

**Perfect Books uses SQLite** - a lightweight, file-based database:

- **Location:** `src/data/perfectbooks.db`
- **No server needed:** Everything runs locally
- **Portable:** Move the folder anywhere, it still works

### Automatic Backups

Your data is **automatically backed up** every time you start the app!

- **Backup Location:** `Documents/PerfectBooks_Data/`
- **Rolling Backups:** 3 daily + 4 weekly backups kept automatically
- **Auto-Restore:** If you delete the app folder and reinstall, your data restores automatically!

**You don't need to do anything** - backups happen silently on startup.

### Manual Backup (Optional)

If you want an extra copy:
```cmd
copy src\data\perfectbooks.db src\data\perfectbooks_backup.db
```

---

## 📝 Summary

| Platform | Startup Method | Browser URL |
|----------|---------------|-------------|
| **Windows** | Double-click `START_WINDOWS.bat` | http://127.0.0.1:5001 |
| **Mac** | Double-click `START_MAC.command` | http://127.0.0.1:5001 |
| **Any Platform** | `python start.py` or `python3 start.py` | http://127.0.0.1:5001 |

---

## 🆘 Still Need Help?

1. **Check the terminal** for error messages (red text)
2. **Verify Python is installed:** `python --version` (should be 3.8+)
3. **Verify packages are installed:** `pip list | findstr Flask`
4. **Check the database exists:** Look for `src/data/perfectbooks.db`
5. **Try the manual method:** `python start.py` to see detailed output

**For Mac users:** See `SETUP_FOR_MAC.txt` for detailed Mac-specific instructions.

---

**Happy budgeting! 💰**
