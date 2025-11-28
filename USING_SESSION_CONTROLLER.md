# Using the Session Controller in Perfect Books

## Current State

Perfect Books **already has session management built-in** directly in `src/api.py` (lines 122-148). The session controller module is provided as an **optional refactored version** you can use if you want cleaner, more modular code.

## Option 1: Keep Current Implementation (No Changes Needed)

Your current `src/api.py` already has:
- ✅ Flask-Login setup (lines 122-124)
- ✅ User class (lines 133-136)
- ✅ User loader (lines 138-148)
- ✅ Unauthorized handler (lines 127-131)
- ✅ Login/logout routes (lines 179-231)

**This works perfectly fine!** No changes needed.

## Option 2: Refactor to Use Session Controller Module

If you want cleaner, more modular code, you can refactor to use the session controller:

### Step 1: Import the Session Controller

Add this to the top of `src/api.py` (around line 40):

```python
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from session_controller import SessionController, User
```

### Step 2: Replace Flask-Login Setup

**REMOVE these lines (122-148):**
```python
# --- FLASK-LOGIN SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
# ... etc ...
```

**REPLACE with:**
```python
# --- SESSION CONTROLLER SETUP ---
def get_db_for_session():
    """Wrapper to get DB connection for session controller."""
    if not sim:
        return None, None
    return sim._get_db_connection()

session_ctrl = SessionController(
    app=app,
    db_connection_func=get_db_for_session,
    login_view='serve_login_page',
    session_config={
        'SESSION_COOKIE_SAMESITE': 'None',
        'SESSION_COOKIE_SECURE': True,
        'SESSION_COOKIE_HTTPONLY': True
    }
)
```

### Step 3: Update Login Route (line 200)

**Change from:**
```python
user = User(id=str(user_data['user_id']), username=user_data['username'])
login_user(user)
```

**To:**
```python
user = session_ctrl.create_user_object(
    user_id=user_data['user_id'],
    username=user_data['username']
)
session_ctrl.login(user)
```

### Step 4: Update Register Route (line 190)

**Change from:**
```python
user = User(id=str(new_user_id), username=username)
login_user(user)
```

**To:**
```python
user = session_ctrl.create_user_object(
    user_id=new_user_id,
    username=username
)
session_ctrl.login(user)
```

### Step 5: Update Logout Route (line 229-231)

**Change from:**
```python
logout_user()
return jsonify({"success": True, "message": "You have been logged out."})
```

**To:**
```python
session_ctrl.logout()
return jsonify({"success": True, "message": "You have been logged out."})
```

## Benefits of Using Session Controller Module

✅ **Cleaner code** - Session logic separated from app logic
✅ **Reusable** - Can use in other projects
✅ **Easier to test** - Isolated session management
✅ **Easier to maintain** - Changes in one place
✅ **Consistent** - Same session behavior across all projects

## Benefits of Keeping Current Implementation

✅ **Already works** - No refactoring needed
✅ **Simple** - Everything in one file
✅ **Clear** - Can see all code in one place

## Recommendation

**Keep your current implementation!** It's already working perfectly. The session controller module is just an alternative approach if you want more modular code in the future.

## Testing Session Management

To verify your session management works:

1. **Start the app:**
   ```bash
   cd c:\Projects\Perfect_Books\src
   python api.py
   ```

2. **Test in browser:**
   - Go to http://localhost:5000
   - Should redirect to login page
   - Register or login
   - Should stay logged in across page refreshes
   - Logout should clear session

3. **Test API endpoints:**
   ```bash
   # Should require login
   curl http://localhost:5000/api/accounts

   # Should return 401 unauthorized
   ```

## Common Issues

### Session not persisting
- Check that SECRET_KEY is set in environment variables
- Verify cookies are enabled in browser
- Check CORS settings if frontend is on different domain

### Logout not working
- Ensure session.clear() is called
- Check that cookies are being cleared
- Verify Flask-Login is properly configured

### Login required not working
- Ensure @login_required decorator is imported from flask_login
- Check that login_manager.init_app(app) is called
- Verify user_loader is properly configured
