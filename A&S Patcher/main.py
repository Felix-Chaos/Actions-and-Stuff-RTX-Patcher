import sys
import os
from src.controllers.appController import AppController  # pylint: disable=wrong-import-position

# Ensure src is in path if needed, though running as module is preferred
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    try:
        app = AppController()
        app.run()
    except KeyboardInterrupt:
        pass
