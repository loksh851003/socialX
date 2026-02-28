import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "site.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, "static", "uploads")