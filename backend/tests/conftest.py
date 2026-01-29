"""
Test configuration - minimal setup since integration tests use real services.
"""
import os

# Set test environment variables
os.environ['JWT_SECRET'] = 'test-secret-value'
