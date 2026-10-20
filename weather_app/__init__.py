"""Application factory for the weather ML web application."""

from flask import Flask

from weather_app.config import Config
from weather_app.routes import api


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    config_object.ensure_runtime_directories()
    app.register_blueprint(api)
    return app
