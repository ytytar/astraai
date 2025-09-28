import uvicorn
from core.fast_api import get_fast_api_app
from dotenv import load_dotenv
import argparse

load_dotenv()

# myapp/__main__.py
import socket
import threading
import time

import webview  # pip install pywebview
import uvicorn

def find_free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    addr, port = s.getsockname()
    s.close()
    return port

def start_server(port):
    app = get_fast_api_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
    # Run Uvicorn in this thread

def wait_for_port(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            try:
                s.settimeout(0.25)
                s.connect(("127.0.0.1", port))
                return True
            except OSError:
                time.sleep(0.1)
    return False

def main():
    port = find_free_port()
    t = threading.Thread(target=start_server, args=(port,), daemon=True)
    t.start()

    if not wait_for_port(port):
        raise RuntimeError("Backend failed to start.")

    # Native window that points to our local server
    webview.create_window("MyApp", f"http://127.0.0.1:{port}", width=1200, height=800)
    # Blocks until the window is closed; when it closes, process exits (daemon thread dies)
    webview.start()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Start the AstraAI application')
    parser.add_argument('--adk-only', action='store_true', 
                       help='Run in ADK-only mode')
    args = parser.parse_args()

    if args.adk_only:
        app = get_fast_api_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        main()

    main()


# if __name__ == "__main__":
#     app = get_fast_api_app()
#     uvicorn.run(app, host="0.0.0.0", port=8000)