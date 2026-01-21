# keystore.py
from cryptography.hazmat.primitives.asymmetric import rsa

# These will be populated at startup by main.py
SIGNING_PRIVATE_KEY: rsa.RSAPrivateKey | None = None
SIGNATURE_PUBLIC_KEY_B64: str = ""
