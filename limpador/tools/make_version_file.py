"""Gera limpapc/_build.py e version_info.txt (metadados do .exe no Windows).

Uso: python tools/make_version_file.py 2.0.15
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ver = sys.argv[1] if len(sys.argv) > 1 else "2.0.0"
parts = [int(x) for x in ver.split(".")] + [0] * 4
t = tuple(parts[:4])

with open(os.path.join(ROOT, "limpapc", "_build.py"), "w", encoding="utf-8") as f:
    f.write(f'VERSION = "{ver}"\n')

with open(os.path.join(ROOT, "version_info.txt"), "w", encoding="utf-8") as f:
    f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', 'LimpaPC'),
      StringStruct('FileDescription', 'LimpaPC - limpeza, otimizacao e recuperacao de arquivos'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'LimpaPC'),
      StringStruct('LegalCopyright', 'Licenca MIT'),
      StringStruct('OriginalFilename', 'LimpaPC.exe'),
      StringStruct('ProductName', 'LimpaPC'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
""")
print("versão", ver)
