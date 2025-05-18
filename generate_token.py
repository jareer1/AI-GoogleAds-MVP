# filename: generate_and_sign_jwt.py
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from datetime import datetime, timedelta

# 1) Generate RSA keypair
private_key_obj = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
public_key_obj = private_key_obj.public_key()

# 2) Serialize keys to PEM format
private_pem = private_key_obj.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),  # or BestAvailableEncryption(b"passphrase")
)
public_pem = public_key_obj.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

# (Optional) write them out if you want persistent files:
with open("private.pem", "wb") as f:
    f.write(private_pem)
with open("public.pem", "wb") as f:
    f.write(public_pem)

