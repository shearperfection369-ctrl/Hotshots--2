# Auth-Gated App Testing Playbook (Tennant TMS)

## Step 1: Create Test User & Session
```bash
mongosh --eval "
use('test_database');
const userId = 'test-user-' + Date.now();
const sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@tennantco.com',
  name: 'Test Dispatcher',
  picture: 'https://via.placeholder.com/150',
  role: 'dispatcher',
  created_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
  created_at: new Date().toISOString()
});
print('SESSION_TOKEN=' + sessionToken);
print('USER_ID=' + userId);
"
```

## Step 2: Test Backend API
```bash
# Read REACT_APP_BACKEND_URL from /app/frontend/.env
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# Test auth endpoint
curl -X GET "$API_URL/api/auth/me" -H "Authorization: Bearer $SESSION_TOKEN"

# Test protected endpoints
curl -X GET "$API_URL/api/shipments" -H "Authorization: Bearer $SESSION_TOKEN"
curl -X GET "$API_URL/api/kpis" -H "Authorization: Bearer $SESSION_TOKEN"
curl -X GET "$API_URL/api/freight-bills" -H "Authorization: Bearer $SESSION_TOKEN"
curl -X GET "$API_URL/api/carriers/onboarding" -H "Authorization: Bearer $SESSION_TOKEN"

# Test driver endpoints (no auth)
curl -X GET "$API_URL/api/driver/shipment/SHP-XXXXXXXX"
```

## Step 3: Browser Testing (Playwright)
```python
await page.context.add_cookies([{
    "name": "session_token",
    "value": SESSION_TOKEN,
    "domain": HOSTNAME,  # without https://
    "path": "/",
    "httpOnly": True,
    "secure": True,
    "sameSite": "None"
}])
await page.goto(f"{API_URL}/dashboard")
```

## Checklist
- [x] User document has `user_id` field (custom UUID, MongoDB's _id is separate)
- [x] Session `user_id` matches user's `user_id` exactly
- [x] All queries use `{"_id": 0}` projection
- [x] Backend queries use `user_id` (not `_id` or `id`)
- [x] API returns user data with `user_id` field
- [x] Browser loads dashboard (not login page) when cookie/header present

## Auth-Free Routes
- `/login`, `/driver`, `/driver/:id`
- Backend: `/api/driver/checkin`, `/api/driver/shipment/{id}`, `/api/auth/session`

## Success Indicators
- ✅ `/api/auth/me` returns 200 with user JSON
- ✅ Protected pages render dashboard content (not redirect to /login)
- ✅ CRUD on shipments, documents, freight-bills works
