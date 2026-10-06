import os
import firebase_admin
from firebase_admin import credentials, firestore

_current_dir = os.path.dirname(os.path.abspath(__file__))
_cert_path = os.path.join(_current_dir, "serviceAccountKey.json")
if not os.path.exists(_cert_path):
    _cert_path = "serviceAccountKey.json"

if not firebase_admin._apps:
    cred = credentials.Certificate(_cert_path)
    firebase_admin.initialize_app(cred)
db = firestore.client()

