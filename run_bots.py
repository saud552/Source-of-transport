import os, sys, time, threading, logging, asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BotManager")

def run_health_server():
    class H(BaseHTTPRequestHandler):
        def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 10000))), H).serve_forever()

def start_bot(name, func):
    logger.info(f"Starting {name} bot...")
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        func()
    except Exception as e:
        logger.error(f"{name} bot failed: {e}", exc_info=True)

if __name__ == "__main__":
    from add.main import main as add_main
    from storage.main import main as storage_main
    from transf.main import main as transfer_main

    threading.Thread(target=run_health_server, daemon=True).start()

    bots = [('Add', add_main), ('Storage', storage_main), ('Transfer', transfer_main)]
    for name, func in bots:
        t = threading.Thread(target=start_bot, args=(name, func), daemon=True)
        t.start()
        time.sleep(5)

    while True:
        time.sleep(10)
