# config.py
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Server listening host
# "127.0.0.1" means only accessible from the local machine
# "0.0.0.0" means accessible from other machines on the network
HOST = "localhost"

# Server listening port
PORT = 80

# Full base URL for the server, used for generating skin links
# Note: If your server is on the public internet, replace HOST with your domain or public IP
BASE_URL = f"http://{HOST}" if PORT == 80 else f"http://{HOST}:{PORT}"

# Custom prefix for the Yggdrasil authentication API
# Example: "/api/pyauthskin" or "/auth"
AUTH_API_PREFIX = "/api/pyauthskin"

# Logging level for Uvicorn and the application
# Options: "debug", "info", "warning", "error", "critical"
LOG_LEVEL = "info"

# CORS configuration
# Allowed origins for CORS (use ["*"] for all in development, specify domains in production)
# 只需修改 config.py 中的 CORS_ALLOWED_ORIGINS 为具体域名列表
CORS_ALLOWED_ORIGINS = ["*"]

# Allow credentials in CORS
CORS_ALLOW_CREDENTIALS = True
# Allowed methods for CORS
CORS_ALLOWED_METHODS = ["*"]
# Allowed headers for CORS
CORS_ALLOWED_HEADERS = ["*"]
