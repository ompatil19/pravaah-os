"""
Admin user management script.

Usage:
  PYTHONPATH=. python scripts/create_admin.py            # create admin
  PYTHONPATH=. python scripts/create_admin.py reset      # reset password interactively
"""
import sys
import uuid

from dotenv import load_dotenv
load_dotenv()

from backend.database import init_db, get_db
from backend.models import User
from backend.auth import hash_password

init_db()

# ── reset mode ───────────────────────────────────────────────────────────────
if len(sys.argv) > 1 and sys.argv[1] == "reset":
    import getpass
    new_pw = getpass.getpass("  New password: ")
    confirm = getpass.getpass("  Confirm password: ")
    if new_pw != confirm:
        print("  ERROR: Passwords do not match.")
        sys.exit(1)
    if len(new_pw) < 6:
        print("  ERROR: Password must be at least 6 characters.")
        sys.exit(1)
    with get_db() as session:
        user = session.query(User).filter(User.username == "admin").first()
        if not user:
            print("  ERROR: admin user not found. Run without 'reset' first.")
            sys.exit(1)
        user.password_hash = hash_password(new_pw)
    print()
    print("  Password updated successfully.")
    print()
    sys.exit(0)

# ── create mode ──────────────────────────────────────────────────────────────
with get_db() as session:
    existing = session.query(User).filter(User.username == "admin").first()

    if existing:
        print()
        print("  Admin user already exists:")
        print(f"  Username : {existing.username}")
        print(f"  User ID  : {existing.id}")
        print(f"  API key  : {existing.api_key}")
        print(f"  Role     : {existing.role}")
        print()
        print("  To reset password: make reset-admin")
        print()
        sys.exit(0)

    key = str(uuid.uuid4())
    user = User(
        username="admin",
        password_hash=hash_password("changeme"),
        role="admin",
        api_key=key,
    )
    session.add(user)
    session.flush()
    uid = user.id

print()
print("  Admin user created:")
print("  Username : admin")
print("  Password : changeme  <-- change this immediately via: make reset-admin")
print(f"  API key  : {key}")
print(f"  User ID  : {uid}")
print()
