"""
Session Controller for Perfect Books
Centralized session management using Flask-Login

This module provides:
- User authentication (register, login, logout)
- Session management with secure cookies
- User loader for Flask-Login
- Protected route decorator

Usage:
    from session_controller import SessionController, User

    # Initialize in your Flask app
    session_ctrl = SessionController(app, get_db_connection_func)

    # Use in routes
    @app.route('/api/protected')
    @login_required
    def protected_route():
        user = session_ctrl.get_current_user()
        return jsonify({"user": user.username})
"""

from flask import jsonify, request, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from functools import wraps


class User(UserMixin):
    """User model for Flask-Login."""

    def __init__(self, id, username, email=None):
        self.id = id
        self.username = username
        self.email = email


class SessionController:
    """
    Manages user sessions and authentication for Flask applications.

    Features:
    - Flask-Login integration
    - Secure session cookies
    - User authentication
    - Protected routes
    """

    def __init__(self, app, db_connection_func, login_view='serve_login_page', session_config=None):
        """
        Initialize the session controller.

        Args:
            app: Flask application instance
            db_connection_func: Function that returns (connection, cursor) tuple
            login_view: Name of the login route (default: 'serve_login_page')
            session_config: Optional dict with session cookie configuration
        """
        self.app = app
        self.get_db = db_connection_func
        self.login_manager = LoginManager()

        # Configure session security
        self._configure_session(session_config)

        # Initialize Flask-Login
        self._init_login_manager(login_view)

    def _configure_session(self, session_config=None):
        """Configure session cookie security settings."""
        if session_config is None:
            session_config = {
                'SESSION_COOKIE_SAMESITE': 'None',
                'SESSION_COOKIE_SECURE': True,
                'SESSION_COOKIE_HTTPONLY': True
            }

        for key, value in session_config.items():
            self.app.config[key] = value

    def _init_login_manager(self, login_view):
        """Initialize Flask-Login with user loader."""
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = login_view

        @self.login_manager.user_loader
        def load_user(user_id):
            """Load user from database by ID."""
            try:
                conn, cursor = self.get_db()
                cursor.execute("SELECT user_id, username FROM users WHERE user_id = %s", (user_id,))
                user_data = cursor.fetchone()
                cursor.close()
                conn.close()

                if user_data:
                    return User(id=str(user_data['user_id']), username=user_data['username'])
                return None
            except Exception as e:
                print(f"Error loading user {user_id}: {e}")
                return None

        @self.login_manager.unauthorized_handler
        def unauthorized():
            """Handle unauthorized access attempts."""
            if request.path.startswith('/api/'):
                return jsonify(success=False, message="Authorization required. Please log in."), 401
            return redirect(url_for(login_view))

    def login(self, user, remember=False):
        """
        Log in a user.

        Args:
            user: User object to log in
            remember: Whether to use a remember-me cookie

        Returns:
            bool: True if successful
        """
        login_user(user, remember=remember)
        return True

    def logout(self):
        """Log out the current user and clear session."""
        logout_user()
        session.clear()
        return True

    def get_current_user(self):
        """
        Get the current logged-in user.

        Returns:
            User object or None if not authenticated
        """
        return current_user if current_user.is_authenticated else None

    def is_authenticated(self):
        """
        Check if a user is currently authenticated.

        Returns:
            bool: True if authenticated, False otherwise
        """
        return current_user.is_authenticated

    def create_user_object(self, user_id, username, email=None):
        """
        Create a User object (helper method).

        Args:
            user_id: User ID
            username: Username
            email: Optional email address

        Returns:
            User object
        """
        return User(id=str(user_id), username=username, email=email)


def login_required_api(f):
    """
    Decorator for API routes that require authentication.
    Returns JSON error instead of redirect.

    Usage:
        @app.route('/api/data')
        @login_required_api
        def get_data():
            return jsonify({"data": "sensitive"})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"success": False, "message": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


# Export commonly used items
__all__ = ['SessionController', 'User', 'login_required_api', 'login_required', 'current_user']
