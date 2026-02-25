"""Shared pytest fixtures for the chatbot test suite.

Provides reusable fixtures for:
- Flask test client
- Mock API responses
- Sample conversation histories
- Settings overrides
"""
import pytest

from app import create_app


@pytest.fixture
def app():
    """Create a Flask application instance for testing."""
    app = create_app()
    app.config["TESTING"] = True
    yield app


@pytest.fixture
def client(app):
    """Create a Flask test client."""
    return app.test_client()
