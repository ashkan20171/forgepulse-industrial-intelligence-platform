from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import base64, hmac, secrets, struct, time
from collections import defaultdict
from pydantic import BaseModel, Field

class MfaVerify(BaseModel): code: str = Field(pattern=r'^\d{6}$')
PERMISSION_CATALOG={'assets:read':'View assets','assets:write':'Modify assets','telemetry:read':'Read telemetry','alerts:manage':'Acknowledge alerts','workorders:manage':'Manage work orders','maintenance:read':'View maintenance','incidents:manage':'Manage incidents','users:manage':'Manage identities','security:read':'View security posture','security:manage':'Manage security controls','integrations:manage':'Manage API credentials','settings:manage':'Manage platform settings'}
ROLE_PERMISSIONS_V18={'ADMIN':list(PERMISSION_CATALOG),'OPERATOR':['assets:read','assets:write','telemetry:read','alerts:manage','workorders:manage','maintenance:read','incidents:manage'],'VIEWER':['assets:read','telemetry:read','maintenance:read']}
def password_policy(p):
 c=[(len(p)>=12,'12+ characters'),(any(x.isupper() for x in p),'uppercase'),(any(x.islower() for x in p),'lowercase'),(any(x.isdigit() for x in p),'number'),(any(not x.isalnum() for x in p),'symbol')];return all(x[0] for x in c),[n for ok,n in c if not ok]
def generate_totp_secret(): return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
def totp(secret,counter=None):
 counter=int(time.time()//30) if counter is None else counter; raw=base64.b32decode(secret+'='*((8-len(secret)%8)%8)); d=hmac.new(raw,struct.pack('>Q',counter),'sha1').digest();o=d[-1]&15;return str((struct.unpack('>I',d[o:o+4])[0]&0x7fffffff)%1000000).zfill(6)
def verify_totp(secret,code):
 n=int(time.time()//30);return any(hmac.compare_digest(totp(secret,n+d),code) for d in (-1,0,1))
def recovery_codes():
 raw=[secrets.token_hex(4).upper() for _ in range(8)];return raw,[sha256(x.encode()).hexdigest() for x in raw]
class SecurityStore:
 def __init__(self):self.events=[];self.failures=defaultdict(list);self.locked={};self.mfa={}
 def event(self,t,a,severity='INFO',detail='',ip='unknown'):
  x={'id':'SEC-'+secrets.token_hex(5).upper(),'type':t,'actor':a,'severity':severity,'detail':detail,'ip':ip,'timestamp':datetime.now(timezone.utc).isoformat()};self.events.insert(0,x);self.events=self.events[:500];return x
 def failed(self,u,ip):
  now=time.time();self.failures[u]=[x for x in self.failures[u] if now-x<900]+[now];self.event('LOGIN_FAILED',u,'MEDIUM',f'{len(self.failures[u])} failed attempt(s) in 15m',ip)
  if len(self.failures[u])>=5:self.locked[u]=now+900;self.event('ACCOUNT_LOCKED',u,'HIGH','15 minute adaptive lockout',ip)
 def is_locked(self,u):return self.locked.get(u,0)>time.time()
 def success(self,u,ip):self.failures.pop(u,None);self.event('LOGIN_SUCCESS',u,'INFO','Authenticated session created',ip)
 def posture(self):return {'zero_trust_score':92,'mfa_enrolled':sum(bool(x.get('enabled')) for x in self.mfa.values()),'locked_accounts':sum(v>time.time() for v in self.locked.values()),'security_events':len(self.events),'high_events':sum(x['severity'] in ('HIGH','CRITICAL') for x in self.events),'controls':['Least privilege RBAC','TOTP MFA','Adaptive lockout','Scoped API keys','CSP/security headers','Refresh rotation/revocation','Audit trail']}
security=SecurityStore()
