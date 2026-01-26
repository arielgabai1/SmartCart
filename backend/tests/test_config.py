"""Tests for environment configuration and secrets management."""
import os
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def test_env_example_exists():
    """Verify .env.example file exists in project root."""
    env_example = PROJECT_ROOT / ".env.example"
    assert env_example.exists(), ".env.example file must exist"


def test_env_example_has_required_keys():
    """Verify .env.example contains OPENAI_API_KEY and MONGO_URI."""
    env_example = PROJECT_ROOT / ".env.example"
    content = env_example.read_text()

    assert "OPENAI_API_KEY" in content, ".env.example must contain OPENAI_API_KEY"
    assert "MONGO_URI" in content, ".env.example must contain MONGO_URI"
    assert "MONGO_INITDB_ROOT_USERNAME" in content, ".env.example must contain MONGO_INITDB_ROOT_USERNAME"
    assert "MONGO_INITDB_ROOT_PASSWORD" in content, ".env.example must contain MONGO_INITDB_ROOT_PASSWORD"


def test_env_example_mongo_uri_value():
    """Verify MONGO_URI in .env.example is set to the correct authenticated value."""
    env_example = PROJECT_ROOT / ".env.example"
    content = env_example.read_text()

    assert "MONGO_URI=mongodb://admin:password@database:27017/smartcart?authSource=admin" in content,         "MONGO_URI must be set to mongodb://admin:password@database:27017/smartcart?authSource=admin"


def test_env_file_exists():
    """Verify .env file exists in project root."""
    env_file = PROJECT_ROOT / ".env"
    assert env_file.exists(), ".env file must exist for local development"


def test_env_file_has_required_keys():
    """Verify .env file contains OPENAI_API_KEY and MONGO_URI."""
    env_file = PROJECT_ROOT / ".env"
    content = env_file.read_text()

    assert "OPENAI_API_KEY" in content, ".env must contain OPENAI_API_KEY"
    assert "MONGO_URI" in content, ".env must contain MONGO_URI"
    assert "MONGO_INITDB_ROOT_USERNAME" in content, ".env must contain MONGO_INITDB_ROOT_USERNAME"
    assert "MONGO_INITDB_ROOT_PASSWORD" in content, ".env must contain MONGO_INITDB_ROOT_PASSWORD"


def test_env_in_gitignore():
    """Verify .env is listed in .gitignore."""
    gitignore = PROJECT_ROOT / ".gitignore"
    content = gitignore.read_text()

    assert ".env" in content, ".env must be in .gitignore to prevent committing secrets"


def test_docker_compose_uses_env_file():
    """Verify docker-compose.yml is configured to use .env file."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"

    with open(compose_file) as f:
        compose_config = yaml.safe_load(f)

    # Check that backend service uses env_file or environment variables from .env
    backend = compose_config.get("services", {}).get("backend", {})

    # Either env_file is specified or environment vars reference ${VAR} syntax
    has_env_file = "env_file" in backend
    env_vars = backend.get("environment", [])

    # Check if environment variables use ${VAR} substitution from .env
    uses_env_substitution = any(
        isinstance(var, str) and ("${" in var or var.startswith("OPENAI_API_KEY") or var.startswith("MONGO_URI"))
        for var in env_vars
    ) if isinstance(env_vars, list) else any(
        "${" in str(val) for val in env_vars.values()
    ) if isinstance(env_vars, dict) else False

    assert has_env_file or uses_env_substitution, \
        "docker-compose.yml backend service must use env_file or reference environment variables from .env"


def test_docker_compose_backend_has_openai_key():
    """Verify backend service in docker-compose.yml has OPENAI_API_KEY configured."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"

    with open(compose_file) as f:
        compose_config = yaml.safe_load(f)

    backend = compose_config.get("services", {}).get("backend", {})
    env_vars = backend.get("environment", [])

    # Check if OPENAI_API_KEY is in environment section
    if isinstance(env_vars, list):
        has_openai = any("OPENAI_API_KEY" in str(var) for var in env_vars)
    elif isinstance(env_vars, dict):
        has_openai = "OPENAI_API_KEY" in env_vars
    else:
        has_openai = False

    # Or check if env_file is specified (which would load all vars from .env)
    has_env_file = "env_file" in backend

    assert has_openai or has_env_file, \
        "Backend service must have access to OPENAI_API_KEY via environment or env_file"


def test_docker_compose_database_has_auth():
    """Verify database service in docker-compose.yml has MongoDB authentication configured."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"

    with open(compose_file) as f:
        compose_config = yaml.safe_load(f)

    database = compose_config.get("services", {}).get("database", {})
    env_vars = database.get("environment", [])

    # Check if MongoDB auth vars are in environment section
    if isinstance(env_vars, list):
        has_username = any("MONGO_INITDB_ROOT_USERNAME" in str(var) for var in env_vars)
        has_password = any("MONGO_INITDB_ROOT_PASSWORD" in str(var) for var in env_vars)
    elif isinstance(env_vars, dict):
        has_username = "MONGO_INITDB_ROOT_USERNAME" in env_vars
        has_password = "MONGO_INITDB_ROOT_PASSWORD" in env_vars
    else:
        has_username = False
        has_password = False

    assert has_username, "Database service must have MONGO_INITDB_ROOT_USERNAME environment variable"
    assert has_password, "Database service must have MONGO_INITDB_ROOT_PASSWORD environment variable"
