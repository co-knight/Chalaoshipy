import os

class Config:
    # secrets.token_hex(24)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-secret-key'