"""Offline-safe backup manifest verification. Does not claim restore success."""
import hashlib,json,sys,pathlib
p=pathlib.Path(sys.argv[1]); data=p.read_bytes(); print(json.dumps({'file':p.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'verified':'checksum-only'}))
