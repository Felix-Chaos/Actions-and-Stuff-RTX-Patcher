"""
Simple Logger for Build System
Usage: python tools/logger.py [TYPE] "Message"
Types: INFO, WARN, ERROR, SUCCESS
"""

import sys
import datetime
import os

# Enable ANSI colors in Windows cmd
os.system("")

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(level, message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    
    level = level.upper()
    
    if level == "INFO":
        color = Colors.CYAN
        icon = "[i]"
    elif level == "WARN":
        color = Colors.WARNING
        icon = "[!]"
    elif level == "ERROR":
        color = Colors.FAIL
        icon = "[X]"
    elif level == "SUCCESS":
        color = Colors.GREEN
        icon = "[OK]"
    else:
        color = Colors.ENDC
        icon = "[?]"

    print(f"{Colors.BOLD}{timestamp} {color}{icon} {message}{Colors.ENDC}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        # Default test
        log("INFO", "This is an info message")
        log("WARN", "This is a warning")
        log("ERROR", "This is an error")
        log("SUCCESS", "This is a success message")
    else:
        log(sys.argv[1], sys.argv[2])
