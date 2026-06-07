#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integrated Bot Manager for Render Production
Includes a health check server and bot orchestration.
"""

import os
import sys
import time
import threading
import logging
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("BotManager")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Health check server listening on port {port}")
    server.serve_forever()

class BotManager:
    def __init__(self):
        self.threads = {}
        self.running = True

    def start_bot(self, name, module):
        try:
            logger.info(f"Starting {name} bot...")
            module.main()
        except Exception as e:
            logger.error(f"Error in {name} bot: {e}")

    def run(self):
        # Import modules dynamically
        try:
            from add import main as add_main
            from storage import main as storage_main
            from transf.main import main as transfer_main
            
            bot_map = {
                'Add': add_main,
                'Storage': storage_main,
                'Transfer': transfer_main
            }
        except Exception as e:
            logger.error(f"Failed to import bot modules: {e}")
            return

        # Start health server in a separate thread
        health_thread = threading.Thread(target=run_health_server, daemon=True)
        health_thread.start()

        # Start bots
        for name, module in bot_map.items():
            t = threading.Thread(target=self.start_bot, args=(name, module), name=f"{name}Thread")
            t.daemon = True
            t.start()
            self.threads[name] = t
            time.sleep(2)

        logger.info("Integrated system is now live and monitoring.")

        try:
            while self.running:
                for name, t in list(self.threads.items()):
                    if not t.is_alive():
                        logger.warning(f"Bot {name} thread died! Attempting restart...")
                        new_t = threading.Thread(target=self.start_bot, args=(name, bot_map[name]), name=f"{name}Thread")
                        new_t.daemon = True
                        new_t.start()
                        self.threads[name] = new_t
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("System shutting down...")
            self.running = False

if __name__ == "__main__":
    manager = BotManager()
    manager.run()
