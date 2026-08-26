import subprocess
from pathlib import Path
from scripts.audit_symlink_targets import audit

def _init_repo(root:Path):
    subprocess.run(['git','init','-q',str(root)],check=True)

def test_symlink_audit_accepts_repository_local_target(tmp_path:Path):
    _init_repo(tmp_path);(tmp_path/'target.txt').write_text('ok',encoding='utf-8');(tmp_path/'link.txt').symlink_to('target.txt');subprocess.run(['git','-C',str(tmp_path),'add','target.txt','link.txt'],check=True);assert audit(tmp_path)==[]

def test_symlink_audit_rejects_external_target(tmp_path:Path):
    root=tmp_path/'repo';root.mkdir();outside=tmp_path/'secret';outside.write_text('x',encoding='utf-8');_init_repo(root);(root/'link').symlink_to(outside);subprocess.run(['git','-C',str(root),'add','link'],check=True);assert audit(root)==['link: symlink target escapes repository']
