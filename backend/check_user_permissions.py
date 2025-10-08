#!/usr/bin/env python3
"""
Script to check user permissions and create admin user if needed.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant

User = get_user_model()

def check_user_permissions():
    """Check and display user permissions."""
    
    print("🔍 CHECKING USER PERMISSIONS")
    print("=" * 50)
    
    # Get all users
    users = User.objects.all()
    
    if not users.exists():
        print("❌ No users found!")
        return
    
    for user in users:
        print(f"\n👤 User: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Is superuser: {user.is_superuser}")
        print(f"   Is staff: {user.is_staff}")
        print(f"   Is active: {user.is_active}")
        print(f"   Tenant: {user.tenant.name if user.tenant else 'None'}")
        print(f"   Role: {user.role}")
        
        # Check if user can manage plans
        can_manage_plans = user.is_superuser or user.is_staff
        print(f"   Can manage plans: {can_manage_plans}")
        
        if not can_manage_plans:
            print(f"   ⚠️  User cannot manage plans - needs admin permissions")
    
    print(f"\n📊 Summary:")
    print(f"   Total users: {users.count()}")
    print(f"   Superusers: {users.filter(is_superuser=True).count()}")
    print(f"   Staff: {users.filter(is_staff=True).count()}")
    print(f"   Active: {users.filter(is_active=True).count()}")

def make_user_admin(username):
    """Make a user admin."""
    
    try:
        user = User.objects.get(username=username)
        user.is_superuser = True
        user.is_staff = True
        user.save()
        print(f"✅ User {username} is now admin!")
    except User.DoesNotExist:
        print(f"❌ User {username} not found!")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        username = sys.argv[1]
        make_user_admin(username)
    else:
        check_user_permissions()
