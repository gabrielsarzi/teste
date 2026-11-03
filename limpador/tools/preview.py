"""Abre o LimpaPC numa página específica e salva um print (para desenvolvimento).

Uso (Linux, precisa de Xvfb e ImageMagick):
    xvfb-run -s "-screen 0 1280x820x24" python3.12 tools/preview.py modulo:Classe saida.png [--dark] [--wait 3000]
          [--exec "codigo python usando a variavel page e app"]
Ex.: ... tools/preview.py limpapc.apps_pages:InstallAppsPage /tmp/x.png --exec "page.populate(DEMO)"
"""
import argparse
import importlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("target")
ap.add_argument("out")
ap.add_argument("--dark", action="store_true")
ap.add_argument("--wait", type=int, default=2500)
ap.add_argument("--exec", default="")
a = ap.parse_args()

from limpapc import gui  # noqa: E402

mod, cls_name = a.target.split(":")
cls = getattr(importlib.import_module(mod), cls_name)
app = gui.App()
if a.dark:
    app.settings["theme"] = "dark"
    app.rebuild("dashboard")
app.page_classes[cls.key] = cls
errors = []
app.report_callback_exception = lambda *e: errors.append(e)


def go():
    app.show(cls.key)
    page = app.page(cls.key)
    if a.exec:
        exec(a.exec, {"page": page, "app": app, **vars(sys.modules[mod])})
    app.after(a.wait, shot)


def shot():
    subprocess.run(["import", "-window", "root", a.out])
    import traceback
    for e in errors:
        traceback.print_exception(*e)
    print("erros:", len(errors))
    app.destroy()


app.after(800, go)
app.mainloop()
