#!/usr/bin/env python3
"""
Generate a test JWT token for M4 testing
This creates a valid token that matches the auth service's secret
"""

import jwt
import datetime
import sys

# Must match the JWT secret in docker-compose.yml
JWT_SECRET = "dev-secret-key-change-in-production-256-bits-minimum"
ALGORITHM = "HS256"

def generate_token(username="testuser", roles=None, person_id="test-person-123"):
    """Generate a test JWT token"""
    if roles is None:
        roles = ["user"]
    
    # Token payload
    payload = {
        "sub": username,  # subject (username)
        "person_id": person_id,
        "roles": roles,
        "username": username,
        "iat": datetime.datetime.utcnow(),  # issued at
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),  # expires in 1 hour
        "token_type": "access"
    }
    
    # Generate token
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    
    return token

def main():
    # Generate tokens for different users
    print("=== M4 Test JWT Tokens ===\n")
    
    # Regular user token
    user_token = generate_token(username="testuser", roles=["user"])
    print(f"User Token (testuser, role: user):")
    print(f"{user_token}\n")
    
    # Admin token
    admin_token = generate_token(username="admin", roles=["admin"], person_id="admin-123")
    print(f"Admin Token (admin, role: admin):")
    print(f"{admin_token}\n")
    
    # Save to file
    with open("m4_test_token.txt", "w") as f:
        f.write(user_token)
    
    print("✅ User token saved to m4_test_token.txt")
    print("\nUsage:")
    print('  $token = Get-Content m4_test_token.txt')
    print('  $headers = @{"Authorization" = "Bearer $token"}')
    print('  Invoke-WebRequest -Uri "http://localhost:8090/ingest" -Headers $headers ...')

if __name__ == "__main__":
    main()
