import sys
import os

# Ensure src is in path if needed, though running as module is preferred
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.controllers.appController import AppController

if __name__ == "__main__":
    app = AppController()
    app.run()
