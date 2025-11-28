# 🚀 How to Start Perfect Books

## The Problem: Terminal Window Closes Immediately

This happens when you double-click `api.py` or `session_controller.py` directly. These are **not** startup files!

## ✅ The Correct Way to Start Perfect Books

### Option 1: Use RUN.bat (Easiest)

1. **Navigate to the Perfect_Books folder:**
   ```
   c:\Projects\Perfect_Books
   ```

2. **Double-click:** `RUN.bat`

3. **A terminal window will stay open** and show:
   ```
   ========================================
     PERFECT BOOKS - Starting Server
   ========================================

   Starting Perfect Books API on port 5000...

   Once started, open your browser to:
     http://localhost:5000
   ```

4. **Open your browser** and go to:
   ```
   http://localhost:5000
   ```

### Option 2: Use Command Prompt (Manual)

1. **Open Command Prompt** (Win + R, type `cmd`, press Enter)

2. **Navigate to Perfect Books:**
   ```cmd
   cd c:\Projects\Perfect_Books\src
   ```

3. **Run the API:**
   ```cmd
   python api.py
   ```

4. **Keep the terminal window open!**

5. **Open your browser** to:
   ```
   http://localhost:5000
   ```

### Option 3: Use PowerShell

1. **Open PowerShell** in Perfect_Books folder
   - Navigate to `c:\Projects\Perfect_Books`
   - Shift + Right-click in folder
   - Select "Open PowerShell window here"

2. **Run:**
   ```powershell
   cd src
   python api.py
   ```

3. **Open browser** to http://localhost:5000

## 🌐 What You Should See

### In the Terminal:
```
============================================================
ENVIRONMENT VARIABLES IN API.PY:
  DB_HOST: localhost
  DB_PORT: 3306
  DB_USER: root
  DB_NAME: perfect_books
  DB_PASSWORD: ***
============================================================
 * Serving Flask app 'api'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

### In the Browser:
You should see the **Perfect Books login page**.

## ❌ Common Mistakes

### ❌ Don't Double-Click These Files:
- `session_controller.py` - This is a **module**, not a startup script
- `api.py` - Double-clicking runs it but the window closes after errors
- `railway_config.py` - This is configuration, not a startup script

### ✅ Do Use These:
- `RUN.bat` - Startup script
- Command Prompt with `python api.py`
- The unified session manager (see below)

## 🎯 Still Not Working?

### Check if MySQL is Running:
```cmd
# Check if MySQL is accessible
mysql -u root -p
```

If MySQL isn't running:
- Start XAMPP (if you use it)
- Or start MySQL service:
  ```cmd
  net start mysql
  ```

### Check if Port 5000 is Already in Use:
```cmd
netstat -ano | findstr :5000
```

If something is using port 5000:
- Close that application
- Or change the port in `src/api.py` line 1292

### Check for Errors:
Run from command prompt to see error messages:
```cmd
cd c:\Projects\Perfect_Books\src
python api.py
```

Leave the window open and read any error messages.

## 🚀 Alternative: Use the Unified Session Manager

Instead of running each project separately, use the unified system:

1. **Run:**
   ```
   c:\Projects\run_all_projects.bat
   ```

2. **Open browser to:**
   ```
   http://localhost:5100
   ```

3. **You'll see a dashboard** with all 3 projects!

## 📝 Summary

| Method | File to Run | Browser URL |
|--------|-------------|-------------|
| **RUN.bat** | Double-click `RUN.bat` | http://localhost:5000 |
| **Command Prompt** | `cd src && python api.py` | http://localhost:5000 |
| **Unified Manager** | `run_all_projects.bat` | http://localhost:5100 |

## 🆘 Need Help?

If you're still seeing the terminal window close:
1. Open Command Prompt manually
2. Navigate to `c:\Projects\Perfect_Books\src`
3. Run `python api.py`
4. **Take a screenshot** of the error message
5. Share the error so we can fix it!
