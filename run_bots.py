import os, sys, time, threading, logging, asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- LD_LIBRARY_PATH INJECTION ---
# TDLib requires libssl.so.1.1 which isn't standard on Render Ubuntu 22.04.
# We download it into the project root. If the project root isn't in LD_LIBRARY_PATH,
# we add it and re-execute the script so the OS linker resolves it natively without breaking Python's ssl.
current_dir = os.path.dirname(os.path.abspath(__file__))
ld_path = os.environ.get("LD_LIBRARY_PATH", "")
if current_dir not in ld_path:
    os.environ["LD_LIBRARY_PATH"] = current_dir + (":" + ld_path if ld_path else "")
    os.execv(sys.executable, [sys.executable] + sys.argv)
# --------------------------------

# Force project root into path
sys.path.insert(0, current_dir)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BotManager")

def run_health_server():

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        def do_HEAD(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), H)
    logger.info(f"Health server live on port {port}")
    server.serve_forever()

def start_bot_thread(name, entry_point):
    logger.info(f"Initializing {name} bot thread...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # entry_point should be the 'main' function which calls asyncio.run or similar
        # Since our main functions now use asyncio.run(run_bot()), they handle their own loop.
        # So we just call the function.
        entry_point()
    except Exception as e:
        logger.error(f"Bot {name} encountered a fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    from add.main import main as add_main
    from storage.main import main as storage_main
    from transf.main import main as transfer_main

    # Start health check server
    threading.Thread(target=run_health_server, daemon=True).start()

    bots = [
        ('AddBot', add_main),
        ('StorageBot', storage_main),
        ('TransferBot', transfer_main)
    ]

    threads = []
    for name, func in bots:
        t = threading.Thread(target=start_bot_thread, args=(name, func), name=name, daemon=True)
        t.start()
        threads.append(t)
        time.sleep(5) # Staggered start

    logger.info("All bot threads launched. Entering monitor loop.")

    while True:
        for t in threads:
            if not t.is_alive():
                logger.error(f"CRITICAL: Thread {t.name} has died!")
        time.sleep(30)
