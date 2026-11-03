"""Páginas de recuperação: restaurar da Lixeira e recuperação profunda de apagados."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .analyzer import category_of
from .pages import ResultsPage
from .recovery import (CARVE_KINDS, Ntfs, RawVolume, carve, detect_fs, is_ssd, list_trash, list_volumes,
                       restore_trash_item)
from .system import empty_recycle_bin
from .utils import IS_WIN, Item, fmt_date, fmt_size, is_admin, open_location


class TrashPage(ResultsPage):
    key, icon = "trash", "trash"
    title = "Restaurar da Lixeira"
    subtitle = ("Tudo o que está na Lixeira, com o local de onde foi apagado. Marque e clique em Restaurar "
                "para devolver os arquivos à pasta original.")
    columns = [("Nome", 280, "w"), ("Tamanho", 95, "e"), ("Apagado em", 110, "center"), ("Local original", 480, "w")]
    scan_label = "Atualizar"
    action_label = "Restaurar selecionados"
    action_style = "Primary.TButton"
    uses_trash = False
    auto_scan = True
    show_open = False
    empty_text = "A Lixeira está vazia."

    def build_actions(self, f):
        ttk.Button(f, text="Esvaziar Lixeira", command=self.empty_bin).pack(side="left")

    def scan_job(self, p, cancel, progress):
        return list_trash(cancel, progress)

    def confirm_text(self, items, to_trash):
        return f"Restaurar {len(items)} item(ns) para o local original?"

    def perform(self, items, to_trash, progress):
        done, errors = [], []
        for it in items:
            progress(f"Restaurando {it.values[0]}…")
            try:
                restore_trash_item(it)
                done.append(it)
            except Exception as e:  # noqa: BLE001
                errors.append((it.values[0], str(e)))
        return done, errors, 0

    def success_text(self, done, freed):
        return f"{len(done)} item(ns) restaurado(s) para o local original"

    def empty_bin(self):
        total = sum(i.size for i in self.all_items)
        if not self.all_items:
            self.app.toast("A Lixeira já está vazia.")
            return
        if messagebox.askyesno("Esvaziar Lixeira", f"Apagar permanentemente {len(self.all_items)} item(ns) "
                               f"({fmt_size(total)})?\n\nDepois disso só a Recuperação profunda pode ajudar.",
                               icon="warning", parent=self):
            try:
                empty_recycle_bin()
                self.app.toast(f"Lixeira esvaziada · {fmt_size(total)} liberados")
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Lixeira", str(e), parent=self)
            self.start_scan()
            self.app.data_changed()


TYPE_FILTERS = ["Todos os tipos", "Imagens", "Vídeos", "Documentos", "Músicas e áudio", "Compactados",
                "Instaladores e ISOs", "Outros"]


class RecoverPage(ResultsPage):
    key, icon = "recover", "download"
    title = "Recuperar apagados"
    subtitle = ("Encontra arquivos apagados definitivamente (Shift+Delete ou Lixeira esvaziada) lendo o disco "
                "diretamente. Funciona melhor em HDs, pendrives e cartões. Em SSDs o próprio disco costuma zerar "
                "os dados apagados (TRIM), e aí a recuperação não é possível. Salve sempre em OUTRA unidade.")
    columns = [("Nome", 240, "w"), ("Tipo", 120, "w"), ("Tamanho", 90, "e"), ("Modificado", 100, "center"),
               ("Chance", 95, "center"), ("Pasta original", 400, "w")]
    scan_label = "Procurar apagados"
    action_label = "Recuperar marcados…"
    action_style = "Primary.TButton"
    uses_trash = False
    show_open = False
    empty_text = ("Escolha a unidade e clique em “Procurar apagados”.\n"
                  "Dica: quanto antes, maior a chance — evite gravar arquivos na unidade até recuperar.")

    def __init__(self, master, app):
        self.volumes = list_volumes()
        self._found: list[Item] = []
        self.ntfs = None
        super().__init__(master, app)
        self.warn = ttk.Label(self.header_right, text="", style="BadgeWarn.TLabel")

    def build_options(self, f):
        self.vol_var = tk.StringVar(value=self.volumes[0][0] if self.volumes else "")
        ttk.Label(f, text="Unidade", style="Card.TLabel").pack(side="left")
        values = [v[0] for v in self.volumes] + ["Arquivo de imagem de disco…"]
        self.vol_box = ttk.Combobox(f, textvariable=self.vol_var, values=values, state="readonly", width=30)
        self.vol_box.pack(side="left", padx=(6, 14))
        self.vol_box.bind("<<ComboboxSelected>>", self._vol_selected)
        self.type_var = tk.StringVar(value=TYPE_FILTERS[0])
        cb = ttk.Combobox(f, textvariable=self.type_var, values=TYPE_FILTERS, state="readonly", width=16)
        cb.pack(side="left", padx=(0, 14))
        cb.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())
        self.good_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Só com boa chance", variable=self.good_only, style="Card.TCheckbutton",
                        command=self.apply_filters).pack(side="left")
        self.image_path = None

    def build_actions(self, f):
        ttk.Button(f, text="Busca por assinatura…", command=self.start_carve).pack(side="left")

    def _vol_selected(self, _=None):
        if self.vol_var.get().startswith("Arquivo de imagem"):
            p = filedialog.askopenfilename(parent=self, title="Imagem de disco (.img, .dd, .raw)")
            if p:
                self.image_path = p
                vals = list(self.vol_box["values"])
                label = f"Imagem: {os.path.basename(p)}"
                if label not in vals:
                    vals.insert(len(vals) - 1, label)
                    self.vol_box["values"] = vals
                self.vol_var.set(label)
            else:
                self.vol_var.set(self.volumes[0][0] if self.volumes else "")

    def _selected_volume(self):
        name = self.vol_var.get()
        if name.startswith("Imagem:") and self.image_path:
            return self.image_path, None
        for label, raw, root in self.volumes:
            if label == name:
                return raw, root
        return None, None

    def _open_volume(self):
        raw, root = self._selected_volume()
        if not raw:
            messagebox.showinfo("Unidade", "Escolha uma unidade ou imagem de disco.", parent=self)
            return None, None
        try:
            return RawVolume(raw), root
        except PermissionError:
            if IS_WIN and not is_admin():
                if messagebox.askyesno("Administrador necessário",
                                       "Para ler o disco diretamente o LimpaOne precisa ser executado como "
                                       "administrador.\n\nReabrir como administrador agora?", parent=self):
                    self.app.elevate()
            else:
                messagebox.showerror("Sem permissão", "Sem permissão para ler esta unidade "
                                     "(no Linux, execute como root).", parent=self)
        except OSError as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a unidade: {e}", parent=self)
        return None, None

    def get_params(self):
        vol, root = self._open_volume()
        if not vol:
            return None
        fs = detect_fs(vol)
        if fs != "NTFS":
            vol.close()
            if messagebox.askyesno("Sistema de arquivos " + fs,
                                   f"Esta unidade usa {fs}. A busca detalhada por nome funciona em NTFS.\n\n"
                                   "Quer usar a Busca por assinatura? Ela varre a unidade inteira procurando fotos, "
                                   "vídeos, PDFs e documentos do Office (os nomes originais não são recuperados).",
                                   parent=self):
                self.start_carve()
            return None
        self._check_ssd(root)
        return {"vol": vol, "root": root}

    def _check_ssd(self, root):
        self.warn.pack_forget()
        if not root:
            return

        def job():
            ssd = is_ssd(root)
            if ssd:
                self.after(0, lambda: (self.warn.config(text="  SSD detectado: chance de recuperação muito baixa  "),
                                       self.warn.pack(side="right")))
        threading.Thread(target=job, daemon=True).start()

    def scan_job(self, p, cancel, progress):
        vol, root = p["vol"], p["root"]
        progress("Lendo a estrutura do disco…")
        self.ntfs = Ntfs(vol)
        self.src_root = root
        files = self.ntfs.scan_deleted(root or "Imagem", cancel, progress)
        items = []
        for f in files:
            cat = category_of(f.name)
            items.append(Item(path=f"{f.path}\\{f.name}", size=f.size,
                              values=(f.name, cat, fmt_size(f.size), fmt_date(f.mtime), f.chance, f.path),
                              raw=(f.name.lower(), cat, f.size, f.mtime,
                                   {"Excelente": 0, "Boa": 1, "Parcial": 2, "Baixa": 3}[f.chance], f.path.lower()),
                              kind="deleted", data={"file": None, "obj": f}))
        items.sort(key=lambda i: (i.raw[4], -i.size))
        progress(f"{len(items)} arquivos apagados encontrados "
                 f"({sum(1 for i in items if i.raw[4] <= 1)} com boa chance de recuperação).")
        return items

    def populate(self, items):
        self._found = list(items or [])
        self.apply_filters()

    def apply_filters(self):
        t = self.type_var.get()
        good = self.good_only.get()
        out = []
        for it in self._found:
            if good and it.raw[4] > 1:
                continue
            if t != TYPE_FILTERS[0] and it.values[1] != t:
                continue
            out.append(it)
        self.all_items = out
        self.render_rows()

    def row_tags(self, item):
        return {"Excelente": ("ok",), "Boa": ("ok",), "Parcial": ("warn",)}.get(item.values[4], ("danger",))

    def run_action(self):
        if self.busy:
            return
        items = self.checked()
        if not items:
            messagebox.showinfo("Nada marcado", "Marque os arquivos que deseja recuperar.", parent=self)
            return
        dest = filedialog.askdirectory(parent=self, title="Onde salvar os arquivos recuperados? (use outra unidade)")
        if not dest:
            return
        if not self._other_drive(dest):
            return
        self._set_busy(True)
        self.run_bg(lambda c, p: self.perform_recover(items, dest, c, p), lambda r: self.after_recover(r, dest),
                    "Recuperando…", on_finally=lambda: self._set_busy(False))

    def _other_drive(self, dest) -> bool:
        root = getattr(self, "src_root", None) or self._selected_volume()[1]
        if root and IS_WIN and os.path.splitdrive(os.path.abspath(dest))[0].upper() == root[:2].upper():
            messagebox.showerror("Escolha outra unidade",
                                 "Salvar na mesma unidade de onde os arquivos foram apagados pode sobrescrever "
                                 "justamente os dados que você quer recuperar.\n\nEscolha um pendrive, HD externo "
                                 "ou outra partição.", parent=self)
            return False
        return True

    def perform_recover(self, items, dest, cancel, progress):
        ok, zeroed, errors = 0, [], []
        for n, it in enumerate(items, 1):
            if cancel.is_set():
                break
            progress(f"Recuperando {n}/{len(items)}: {it.values[0]}")
            try:
                _, good = self.ntfs.recover(it.data["obj"], dest)
                ok += 1
                if not good:
                    zeroed.append(it.values[0])
            except Exception as e:  # noqa: BLE001
                errors.append((it.values[0], str(e)))
        return ok, zeroed, errors

    def after_recover(self, result, dest):
        ok, zeroed, errors = result
        if ok:
            self.app.toast(f"{ok} arquivo(s) recuperado(s) em {dest}")
            open_location(dest)
        if zeroed or errors:
            msg = ""
            if zeroed:
                msg += (f"{len(zeroed)} arquivo(s) foram gravados, mas o conteúdo está zerado — o disco já "
                        "apagou esses dados (comum em SSD):\n" + "\n".join(f"• {z}" for z in zeroed[:10]) + "\n\n")
            if errors:
                msg += "Erros:\n" + "\n".join(f"• {n}: {m}" for n, m in errors[:10])
            messagebox.showwarning("Recuperação", msg.strip(), parent=self)

    # ---- busca por assinatura ----
    def start_carve(self):
        if self.busy:
            return
        vol, root = self._open_volume()
        if not vol:
            return
        kinds = ", ".join(CARVE_KINDS.values())
        if not messagebox.askyesno("Busca por assinatura",
                                   f"A unidade inteira ({fmt_size(vol.size)}) será lida procurando:\n{kinds}.\n\n"
                                   "Os arquivos encontrados (inclusive os que ainda existem) são salvos com nomes "
                                   "numerados. Pode demorar bastante em unidades grandes.\n\nContinuar?", parent=self):
            vol.close()
            return
        dest = filedialog.askdirectory(parent=self, title="Onde salvar os arquivos encontrados? (use outra unidade)")
        if not dest:
            vol.close()
            return
        self.src_root = root
        if not self._other_drive(dest):
            vol.close()
            return
        dest = os.path.join(dest, "LimpaOne - recuperados")
        os.makedirs(dest, exist_ok=True)

        def done(counts):
            vol.close()
            total = sum(counts.values())
            self.app.toast(f"Busca concluída: {total} arquivo(s) salvos")
            if total:
                open_location(dest)

        self._set_busy(True)
        self.run_bg(lambda c, p: carve(vol, dest, list(CARVE_KINDS), c, p), done, "Varrendo o disco…",
                    on_finally=lambda: self._set_busy(False))
