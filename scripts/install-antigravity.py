"""Download the official CLI to this project, verify upstream SHA-512, no shell setup."""
import hashlib
import io
import json
import platform
import tarfile
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parent.parent
system={'Darwin':'darwin','Linux':'linux'}.get(platform.system())
arch={'arm64':'arm64','aarch64':'arm64','x86_64':'amd64'}.get(platform.machine())
if not system or not arch:
    raise SystemExit('Use the official installer for this platform.')
url='https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/'+system+'_'+arch+'.json'
manifest=json.load(urllib.request.urlopen(url,timeout=30))
payload=urllib.request.urlopen(manifest['url'],timeout=120).read()
if hashlib.sha512(payload).hexdigest()!=manifest['sha512']:
    raise SystemExit('Upstream checksum mismatch; not installed.')
if '.tar.gz' in manifest['url']:
    with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
        payload=archive.extractfile('antigravity').read()
target=root/'tools'/'bin'/'agy'
if target.exists():
    raise SystemExit('Already installed. Update explicitly using the official CLI.')
target.parent.mkdir(parents=True,exist_ok=True)
target.write_bytes(payload)
target.chmod(0o755)
(root/'evidence'/'antigravity-install.json').write_text(json.dumps({'version':manifest['version'],'manifest':url,'download_url':manifest['url'],'sha512':manifest['sha512'],'checksum_verified':True,'target':str(target)},indent=2))
print('Installed',manifest['version'],'at',target)
