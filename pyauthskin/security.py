# security.py
from passlib.context import CryptContext

# Define the password context once and import it where needed
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
