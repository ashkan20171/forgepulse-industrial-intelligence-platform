from app.security_zero_trust import password_policy, generate_totp_secret, totp, verify_totp, ROLE_PERMISSIONS_V18

def test_strong_password_policy():
    assert password_policy('StrongPassword!2026')[0]
    assert not password_policy('weak')[0]

def test_totp_roundtrip():
    secret=generate_totp_secret(); code=totp(secret); assert verify_totp(secret,code)

def test_least_privilege_roles():
    assert 'security:manage' in ROLE_PERMISSIONS_V18['ADMIN']
    assert 'security:manage' not in ROLE_PERMISSIONS_V18['OPERATOR']
    assert 'assets:write' not in ROLE_PERMISSIONS_V18['VIEWER']
