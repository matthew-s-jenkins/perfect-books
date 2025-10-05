"""
Perfect Books v2.1 - Desktop Launcher
Starts the Flask server and opens the browser automatically.
"""
import os
import sys
import webbrowser
import time
import threading

# Get the base directory
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    BASE_DIR = sys._MEIPASS
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Add src directory to path
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

def open_browser():
    """Open browser after a short delay"""
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:5000/index.html')

if __name__ == '__main__':
    print("=" * 60)
    print(" Perfect Books v2.1")
    print("=" * 60)
    print("\nStarting server...")

    # Start browser in background thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Import and run Flask app
    from api import app
    print("\nServer running at http://127.0.0.1:5000")
    print("Opening browser...")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)

    app.run(host='127.0.0.1', port=5000, debug=False)
