#!/usr/bin/env python3
"""
JanSakshi Judge Demo Database Seeder
CLI script to idempotently initialize departments, dedicated judge demo accounts,
and realistic dummy complaints for the 10-Day Hackathon Evaluation.

Usage:
    python seed_judge_demo.py
"""

import sys
import os

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.judge_demo_service import seed_judge_demo_data

def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python seed_judge_demo.py [--force-demo-seed]")
        print("Options:")
        print("  --force-demo-seed   Explicitly authorize one-time demo seeding against the dedicated demo database")
        print("\nSafety note: The --force-demo-seed flag may authorize seeding ONLY against dedicated demo databases.")
        print("It can NEVER bypass protection for the real JanSakshi production database.")
        sys.exit(0)

    force_allow = "--force-demo-seed" in sys.argv

    print("=============================================================")
    print("JanSakshi: Initializing 10-Day Hackathon Judge Demo Data")
    print("=============================================================")

    db = SessionLocal()
    try:
        result = seed_judge_demo_data(db, force_allow=force_allow)
        print(f"Status: {result['status']}")
        print(f"Seeded Demo Complaints: {result['seeded_complaints_count']}")
        print("Dedicated Demo Accounts:")
        for role, username in result["demo_accounts"].items():
            print(f"  - Role: {role.ljust(20)} Username: {username}")
        print("\nNote: Passwords are non-public, cryptographically random bcrypt hashes.")
        print("Judges authenticate securely via one-click API: /api/auth/judge-demo/{role}")
        print("=============================================================")
    except PermissionError as pe:
        print(f"\n[BLOCKED] {pe}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error seeding judge demo data: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
