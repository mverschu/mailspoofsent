from cryptography.fernet import Fernet
import os

# Path to the key file
KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.encryption_key')

def generate_key():
    """
    Generates a new encryption key and saves it to the key file.
    """
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as key_file:
        key_file.write(key)

def load_key():
    """
    Loads the encryption key from the key file.
    If the key file does not exist, it generates a new key.
    """
    if not os.path.exists(KEY_FILE):
        generate_key()
    with open(KEY_FILE, 'rb') as key_file:
        return key_file.read()

def encrypt_password(password):
    """
    Encrypts a password using the encryption key.
    """
    key = load_key()
    fernet = Fernet(key)
    encrypted_password = fernet.encrypt(password.encode())
    return encrypted_password.decode()

def decrypt_password(encrypted_password):
    """
    Decrypts an encrypted password using the encryption key.
    """
    key = load_key()
    fernet = Fernet(key)
    decrypted_password = fernet.decrypt(encrypted_password.encode())
    return decrypted_password.decode()
