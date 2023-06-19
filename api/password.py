import bcrypt

# TODO: use .env instead
f = open("pwd_hash", 'r') # file contains the hash (str) returned from "hash_password"
password_hash = f.read().encode("utf-8")
f.close()

_bcrypt_rounds = 12

def hash_password(plain_text_password:str):
    return bcrypt.hashpw(plain_text_password.encode("utf-8"), bcrypt.gensalt(_bcrypt_rounds))

def check_password(plain_text_password:str):
    return bcrypt.checkpw(plain_text_password.encode("utf-8"), password_hash)
