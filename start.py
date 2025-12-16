#!/usr/bin/env python3
"""
Perfect Books - Simple Launcher

This script handles:
1. Python version check (requires 3.8+)
2. Dependency verification
3. Database setup (creates if missing)
4. Migration runner (applies pending migrations)
5. Flask server startup
6. Auto-opens browser

Usage:
    python start.py

Or double-click START_WINDOWS.bat (Windows) or START_MAC.command (Mac)
"""

import sys
import os
import webbrowser
import time
from pathlib import Path


def check_python_version():
    """Verify Python 3.8+ is installed"""
    print("[1/5] Checking Python version...", end=" ")

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
    print("[2/5] Checking dependencies...", end=" ")

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
    """Initialize database if first run, or run migrations if exists"""
    db_path = Path(__file__).parent / "src" / "data" / "perfectbooks.db"

    if not db_path.exists():
        print("[3/5] First time setup! Creating database...", end=" ")

        # Import and run database setup
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
        print("[3/5] Database found...", end=" ")
        print("[OK]")

        # Check for pending migrations
        print("[4/5] Checking for migrations...", end=" ")
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from migration_runner import run_all_pending

        applied = run_all_pending()
        if applied > 0:
            print(f"[OK] Applied {applied} migration(s)")
        else:
            print("[OK] No pending migrations")


def start_flask_server():
    """Launch Flask API server and auto-open browser"""
    print("[5/5] Starting Perfect Books server...")
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
