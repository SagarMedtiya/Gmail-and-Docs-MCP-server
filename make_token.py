from auth import authenticate

creds = authenticate()
print(f"token saved. expires_at={creds.expiry} scopes={creds.scopes}")