from flask import Flask
from database import init_db

def create_app():
    app = Flask(__name__)
    app.secret_key = "dev-secret-key"
    from .routes import main
    app.register_blueprint(main)
    init_db()
    return app