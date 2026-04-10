from flask import Flask
from models import db, bcrypt, login_manager
from auth import auth_bp
from routes import main_bp
import os

gunicorn app:create_app():
    if __name__ =="__main__"
    app.run()
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key_for_development_only')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///finance.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
