from flask import Flask
from flask_migrate import Migrate
from flask_socketio import SocketIO
from extensions import db, login_manager
import os
import socket

app = Flask(__name__)
database_url = os.environ.get("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SECRET_KEY"] = "supersecretkey"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()

migrate = Migrate(app, db)

socketio = SocketIO(app, cors_allowed_origins="*")

from routes import *

def create_app():
    app = Flask(__name__)
    return app
    
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    ip = get_local_ip()
    print("Server Running On:")
    print(f"http://{ip}:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)