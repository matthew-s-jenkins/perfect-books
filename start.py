#!/usr/bin/env python3
"""
Perfect Books - Simple Launcher

This script handles:
1. Python version check (requires 3.8+)
2. Dependency verification
3. Database setup (creates if missing, restores from backup if available)
4. Automatic backup to Documents/PerfectBooks_Data
5. Migration runner (applies pending migrations)
6. Flask server startup
7. Auto-opens browser

Usage:
    python start.py

Or double-click START_WINDOWS.bat (Windows) or START_MAC.command (Mac)
"""

import sys
import os
import webbrowser
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta


# =============================================================================
# BACKUP AND RESTORE FUNCTIONS
# =============================================================================

def get_backup_dir():
    """Get cross-platform Documents/PerfectBooks_Data path"""
    if sys.platform == 'win32':
        docs = Path(os.environ.get('USERPROFILE', str(Path.home()))) / 'Documents'
    else:  # macOS/Linux
        docs = Path.home() / 'Documents'

    backup_dir = docs / 'PerfectBooks_Data'
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def backup_database(db_path):
    """
    Backup database to Documents/PerfectBooks_Data
    - Always copy to perfectbooks.db (latest)
    - Daily: perfectbooks_YYYY-MM-DD.db (keep 3)
    - Weekly: perfectbooks_week-NN.db on Sundays (keep 4)
    """
    if not db_path.exists():
        return False, "No database to backup"

    backup_dir = get_backup_dir()
    daily_dir = backup_dir / 'daily'
    weekly_dir = backup_dir / 'weekly'
    daily_dir.mkdir(exist_ok=True)
    weekly_dir.mkdir(exist_ok=True)

    today = datetime.now()

    # 1. Always copy to latest
    shutil.copy2(db_path, backup_dir / 'perfectbooks.db')

    # 2. Daily backup (once per day)
    daily_file = daily_dir / f"perfectbooks_{today.strftime('%Y-%m-%d')}.db"
    if not daily_file.exists():
        shutil.copy2(db_path, daily_file)

    # 3. Weekly backup (on Sundays)
    if today.weekday() == 6:  # Sunday
        week_num = today.isocalendar()[1]
        weekly_file = weekly_dir / f"perfectbooks_week-{week_num:02d}.db"
        if not weekly_file.exists():
            shutil.copy2(db_path, weekly_file)

    # 4. Cleanup old backups
    cleanup_old_daily_backups(daily_dir, days=3)
    cleanup_old_weekly_backups(weekly_dir, weeks=4)

    return True, str(backup_dir)


def cleanup_old_daily_backups(daily_dir, days=3):
    """Delete daily backups older than N days"""
    cutoff = datetime.now() - timedelta(days=days)
    for f in daily_dir.glob('perfectbooks_*.db'):
        try:
            # Parse date from filename
            date_str = f.stem.replace('perfectbooks_', '')
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            if file_date < cutoff:
                f.unlink()
        except (ValueError, OSError):
            pass  # Skip files that don't match pattern


def cleanup_old_weekly_backups(weekly_dir, weeks=4):
    """Keep only the most recent N weekly backups"""
    files = sorted(weekly_dir.glob('perfectbooks_week-*.db'), reverse=True)
    for f in files[weeks:]:  # Delete all beyond the first N
        try:
            f.unlink()
        except OSError:
            pass


def find_latest_backup():
    """Find the most recent backup for restore"""
    try:
        backup_dir = get_backup_dir()
        latest = backup_dir / 'perfectbooks.db'

        if latest.exists():
            mtime = datetime.fromtimestamp(latest.stat().st_mtime)
            return latest, mtime
    except Exception:
        pass

    return None, None


def restore_database(db_path):
    """Restore database from backup if available"""
    backup_file, backup_date = find_latest_backup()

    if backup_file is None:
        return False, None

    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy backup to database location
    shutil.copy2(backup_file, db_path)

    return True, backup_date


# =============================================================================
# STARTUP CHECKS
# =============================================================================


def check_python_version():
    """Verify Python 3.8+ is installed"""
    print("[1/6] Checking Python version...", end=" ")

    if sys.version_info < (3, 8):
        print("[ERROR]")
        print()
        print("=" * 60)
        print("ERROR: Python 3.8 or higher is required")
        print("=" * 60)
        print(f"You are using Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        print()
        print("Please install Python 3.8+ from https://www.python.org/downloads/")
        print()
        input("Press Enter to exit...")
        sys.exit(1)

    print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")


def check_dependencies():
    """Verify required packages are installed"""
    print("[2/6] Checking dependencies...", end=" ")

    missing = []
    required = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
        'flask_login': 'Flask-Login',
        'bcrypt': 'bcrypt',
        'dotenv': 'python-dotenv'
    }

    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print("[ERROR]")
        print()
        print("=" * 60)
        print("ERROR: Missing required packages")
        print("=" * 60)
        print()
        print("Missing packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print()
        print("To install all dependencies, run:")
        print("  pip install -r requirements.txt")
        print()
        input("Press Enter to exit...")
        sys.exit(1)

    print("[OK]")


def setup_database():
    """Initialize database if first run, restore from backup, or run migrations"""
    db_path = Path(__file__).parent / "src" / "data" / "perfectbooks.db"

    if not db_path.exists():
        # Try to restore from backup first
        print("[3/6] Database not found...", end="")

        restored, backup_date = restore_database(db_path)

        if restored:
            print()
            print(f"      Found backup from {backup_date.strftime('%B %d, %Y')}")
            print("      Restoring your data...", end=" ")
            print("[OK] Welcome back!")
        else:
            # No backup exists - first time setup
            print()
            print("      Creating new database...", end=" ")

            sys.path.insert(0, str(Path(__file__).parent / "src"))
            from setup_sqlite import create_database

            success = create_database()
            if success:
                print("[OK]")
            else:
                print("[ERROR]")
                print()
                print("Failed to create database. Check error messages above.")
                input("Press Enter to exit...")
                sys.exit(1)
    else:
        print("[3/6] Database found...", end=" ")
        print("[OK]")

    # Backup the database
    print("[4/6] Backing up your data...", end=" ")
    if db_path.exists():
        success, location = backup_database(db_path)
        if success:
            print("[OK] Saved to Documents/PerfectBooks_Data")
        else:
            print("[SKIP] No data yet")
    else:
        print("[SKIP] First run - no data to backup yet")

    # Check for pending migrations
    print("[5/6] Checking for migrations...", end=" ")
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from migration_runner import run_all_pending

    applied = run_all_pending()
    if applied > 0:
        print(f"[OK] Applied {applied} migration(s)")
    else:
        print("[OK] No pending migrations")


def start_flask_server():
    """Launch Flask API server and auto-open browser"""
    print("[6/6] Starting Perfect Books server...")
    print()
    print("=" * 60)
    print("Perfect Books is running!")
    print("=" * 60)
    print()
    print("  Server: http://127.0.0.1:5001")
    print("  Press Ctrl+C to stop the server")
    print()

    # Auto-open browser after short delay
    def open_browser():
        time.sleep(1.5)
        try:
            webbrowser.open("http://127.0.0.1:5001/login")
        except:
            pass  # Browser opening is optional

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # Change to src directory and start Flask
    os.chdir(Path(__file__).parent / "src")

    # Import and run Flask app
    from api import app
    app.run(debug=False, port=5001, use_reloader=False)


def main():
    """Main entry point"""
    print()
    print("=" * 60)
    print("Perfect Books - Personal Finance Manager")
    print("=" * 60)
    print()

    try:
        check_python_version()
        check_dependencies()
        setup_database()
        start_flask_server()
    except KeyboardInterrupt:
        print()
        print()
        print("=" * 60)
        print("Server stopped. Thank you for using Perfect Books!")
        print("=" * 60)
        print()
    except Exception as e:
        print()
        print()
        print("=" * 60)
        print("ERROR: An unexpected error occurred")
        print("=" * 60)
        print()
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        print()
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
