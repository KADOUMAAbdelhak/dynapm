"""Optional pinned local CLI installer. Explicit invocation only; no global writes."""
import argparse,hashlib,json,os,platform,urllib.request
from pathlib import Path


def install(repo,cache=None):
    repo=Path(repo).resolve();d=json.loads((repo/'configs/system_validation_v1.json').read_text())['kubernetes']
    machine={'aarch64':'arm64','x86_64':'amd64'}.get(platform.machine(),platform.machine())
    key=platform.system().lower()+'-'+machine
    if key not in d['tools_by_platform']:raise ValueError('installer_platform_not_frozen; provide matching CLI versions on PATH')
    destination=repo/d['tools_directory'];destination.mkdir(parents=True,exist_ok=True)
    for name,spec in d['tools_by_platform'][key].items():
        local=Path(cache)/name if cache else destination/name
        if local.is_file():data=local.read_bytes()
        else:
            with urllib.request.urlopen(spec['url'],timeout=60) as response:data=response.read()
        if hashlib.sha256(data).hexdigest()!=spec['sha256']:raise ValueError('cli_binary_hash_mismatch:'+name)
        target=destination/name;temporary=destination/(name+'.partial')
        temporary.write_bytes(data);temporary.chmod(0o755);os.replace(temporary,target)
    return destination


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--cache',type=Path)
    a=p.parse_args();print(install(a.repo,a.cache))

if __name__=='__main__':main()
