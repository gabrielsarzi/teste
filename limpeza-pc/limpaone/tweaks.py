"""Ajustes reversíveis do Windows (desempenho, privacidade e conveniência).

Cada ajuste grava um ou mais valores no registro. Antes de aplicar, o valor ORIGINAL de cada um é
guardado (em app.settings["tweaks_backup"]) para que "Desfazer" devolva exatamente o que havia antes.
O acesso ao registro passa por uma pequena interface (WinRegStore / MemoryStore) para que a lógica
possa ser testada em qualquer sistema.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field

from .utils import IS_WIN, NO_WINDOW, is_admin, log

if IS_WIN:
    import winreg  # type: ignore

DWORD, SZ = "DWORD", "SZ"


@dataclass
class RegValue:
    hive: str          # "HKCU" ou "HKLM"
    key: str
    name: str
    kind: str          # DWORD | SZ
    on: object         # valor quando o ajuste está aplicado
    default: object = None   # padrão do Windows (None = valor não existe) — usado se não houver backup


@dataclass
class Tweak:
    id: str
    group: str
    title: str
    desc: str
    values: list[RegValue]
    recommended: bool = False
    restart: str = ""        # "" | "explorer" | "logoff" | "reboot"
    note: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def admin(self) -> bool:
        return any(v.hive == "HKLM" for v in self.values)


_ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
_CDM = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"

TWEAKS: list[Tweak] = [
    # ------------------------------------------------------------ desempenho
    Tweak("menu_delay", "Desempenho", "Menus mais rápidos",
          "Os menus e submenus abrem quase na hora, sem a pequena espera padrão do Windows.",
          [RegValue("HKCU", r"Control Panel\Desktop", "MenuShowDelay", SZ, "100", "400")],
          recommended=True, restart="logoff"),
    Tweak("transparency", "Desempenho", "Desativar efeitos de transparência",
          "Barra de tarefas e menu Iniciar ficam opacos. Alivia um pouco a placa de vídeo em PCs mais fracos.",
          [RegValue("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                    "EnableTransparency", DWORD, 0, 1)]),
    Tweak("gamedvr", "Desempenho", "Desativar gravação de jogos em segundo plano",
          "Impede que o Xbox Game Bar fique gravando os jogos o tempo todo, o que pesa no desempenho.",
          [RegValue("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", DWORD, 0, 1),
           RegValue("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", DWORD, 0, None)],
          recommended=True),
    Tweak("bgapps", "Desempenho", "Desativar apps em segundo plano",
          "Apps da Microsoft Store deixam de rodar escondidos. Alguns podem parar de mostrar notificações.",
          [RegValue("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                    "GlobalUserDisabled", DWORD, 1, None),
           RegValue("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BackgroundAppGlobalToggle",
                    DWORD, 0, None)],
          restart="logoff"),
    # ------------------------------------------------------------ privacidade
    Tweak("adid", "Privacidade", "Desativar ID de anúncio",
          "Os apps deixam de usar um identificador seu para mostrar propaganda personalizada.",
          [RegValue("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", DWORD, 0, None)],
          recommended=True),
    Tweak("suggestions", "Privacidade", "Sem dicas, sugestões e apps patrocinados",
          "Para de instalar apps de propaganda sozinho e esconde sugestões no Iniciar, nas Configurações e "
          "na tela de bloqueio.",
          [RegValue("HKCU", _CDM, n, DWORD, 0, None) for n in (
              "SilentInstalledAppsEnabled", "SystemPaneSuggestionsEnabled", "SoftLandingEnabled",
              "PreInstalledAppsEnabled", "OemPreInstalledAppsEnabled", "SubscribedContent-338388Enabled",
              "SubscribedContent-338389Enabled", "SubscribedContent-353694Enabled",
              "SubscribedContent-353696Enabled", "SubscribedContent-310093Enabled")],
          recommended=True),
    Tweak("bing", "Privacidade", "Pesquisa do Iniciar sem Bing",
          "A busca do menu Iniciar procura só no seu computador, sem enviar o que você digita para a internet.",
          [RegValue("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", DWORD, 0, None),
           RegValue("HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions",
                    DWORD, 1, None)],
          recommended=True, restart="explorer"),
    Tweak("activity", "Privacidade", "Desativar histórico de atividades",
          "O Windows para de registrar e enviar quais programas e arquivos você abriu (Linha do Tempo).",
          [RegValue("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", n, DWORD, 0, None)
           for n in ("EnableActivityFeed", "PublishUserActivities", "UploadUserActivities")],
          recommended=True),
    Tweak("telemetry", "Privacidade", "Telemetria no nível mínimo",
          "Reduz os dados de diagnóstico enviados à Microsoft ao mínimo permitido pela sua edição do Windows.",
          [RegValue("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", DWORD, 1, None)],
          recommended=True, restart="reboot",
          note="Nas edições Home e Pro o mínimo é “dados obrigatórios”."),
    # ------------------------------------------------------------ conveniência
    Tweak("ext", "Conveniência", "Mostrar extensões de arquivo",
          "Mostra o final do nome (.pdf, .exe, .jpg…). Ajuda a perceber arquivos falsos, como “foto.jpg.exe”.",
          [RegValue("HKCU", _ADV, "HideFileExt", DWORD, 0, 1)], recommended=True, restart="explorer"),
    Tweak("hidden", "Conveniência", "Mostrar arquivos ocultos",
          "Exibe arquivos e pastas escondidos (aparecem um pouco mais claros no Explorador).",
          [RegValue("HKCU", _ADV, "Hidden", DWORD, 1, 2)], restart="explorer"),
    Tweak("thispc", "Conveniência", "Abrir o Explorador em “Este Computador”",
          "O Explorador de Arquivos abre mostrando os discos, em vez da página Início/Acesso rápido.",
          [RegValue("HKCU", _ADV, "LaunchTo", DWORD, 1, None)], restart="explorer"),
]
TWEAK_BY_ID = {t.id: t for t in TWEAKS}
GROUPS = ["Desempenho", "Privacidade", "Conveniência"]
GROUP_INFO = {
    "Desempenho": ("bolt", "Deixa o Windows mais leve e responsivo."),
    "Privacidade": ("shield", "Menos propaganda e menos dados enviados à Microsoft."),
    "Conveniência": ("folder", "Pequenas melhorias no Explorador de Arquivos."),
}
RESTART_TEXT = {"explorer": "Reinicia o Explorer", "logoff": "Vale ao entrar de novo", "reboot": "Vale após reiniciar"}


# =================================================================== acesso ao registro
class MemoryStore:
    """Registro falso em memória (testes e prévias): {(hive, key_lower, name): (kind, data)}."""

    def __init__(self, data=None, admin=True):
        self.data = {}
        self.admin = admin
        for (hive, key, name), val in (data or {}).items():
            self.data[(hive, key.lower(), name)] = val

    def get(self, hive, key, name):
        return self.data.get((hive, key.lower(), name))

    def write_many(self, ops):
        if not self.admin and any(op[0] == "HKLM" for op in ops):
            raise PermissionError("permissão de administrador negada")
        for hive, key, name, kind, data in ops:
            if kind is None:
                self.data.pop((hive, key.lower(), name), None)
            else:
                self.data[(hive, key.lower(), name)] = (kind, data)


_KIND_TO_WIN = {"DWORD": 4, "SZ": 1, "EXPAND_SZ": 2, "MULTI_SZ": 7, "BINARY": 3, "QWORD": 11}
_WIN_TO_KIND = {v: k for k, v in _KIND_TO_WIN.items()}
_REG_EXE_TYPE = {"DWORD": "REG_DWORD", "SZ": "REG_SZ", "EXPAND_SZ": "REG_EXPAND_SZ", "QWORD": "REG_QWORD",
                 "MULTI_SZ": "REG_MULTI_SZ", "BINARY": "REG_BINARY"}


class WinRegStore:
    """Registro real (Windows). HKLM sempre na visão 64 bits."""

    @staticmethod
    def _root(hive):
        return winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER

    def get(self, hive, key, name):
        try:
            with winreg.OpenKey(self._root(hive), key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                data, typ = winreg.QueryValueEx(k, name)
        except OSError:
            return None
        return (_WIN_TO_KIND.get(typ, str(typ)), data)

    def _write_direct(self, ops):
        for hive, key, name, kind, data in ops:
            root = self._root(hive)
            if kind is None:
                try:
                    with winreg.OpenKey(root, key, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
                        winreg.DeleteValue(k, name)
                except FileNotFoundError:
                    pass
            else:
                with winreg.CreateKeyEx(root, key, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
                    winreg.SetValueEx(k, name, 0, _KIND_TO_WIN.get(kind, 1), data)

    def write_many(self, ops):
        user = [o for o in ops if o[0] != "HKLM"]
        machine = [o for o in ops if o[0] == "HKLM"]
        self._write_direct(user)
        if not machine:
            return
        if is_admin():
            self._write_direct(machine)
            return
        # sem admin: um único pedido de UAC para todos os valores de HKLM
        from .winutil import run_ps_elevated
        rc, _ = run_ps_elevated(elevated_script(machine), timeout=300)
        if rc == -1:
            raise PermissionError("permissão de administrador negada")
        # confere se gravou
        for hive, key, name, kind, data in machine:
            cur = self.get(hive, key, name)
            if (kind is None and cur is not None) or (kind is not None and (cur is None or cur[1] != data)):
                raise PermissionError(f"não foi possível alterar {hive}\\{key}\\{name}")


def _ps_quote(s) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def elevated_script(ops) -> str:
    """Script PowerShell (executado como admin) que grava os valores com reg.exe na visão 64 bits."""
    lines = []
    for hive, key, name, kind, data in ops:
        path = _ps_quote(f"{hive}\\{key}")
        if kind is None:
            lines.append(f"& reg.exe delete {path} /v {_ps_quote(name)} /f /reg:64 | Out-Null")
        else:
            if kind == "BINARY" and isinstance(data, (bytes, bytearray)):
                data = data.hex()
            elif kind == "MULTI_SZ" and isinstance(data, (list, tuple)):
                data = "\\0".join(data)
            lines.append(f"& reg.exe add {path} /v {_ps_quote(name)} /t {_REG_EXE_TYPE.get(kind, 'REG_SZ')} "
                         f"/d {_ps_quote(data)} /f /reg:64 | Out-Null")
    lines.append("@{ok=$true} | ConvertTo-Json | Set-Content -Encoding UTF8 $out")
    return "\n".join(lines)


def default_store():
    return WinRegStore() if IS_WIN else None


# =================================================================== estado / aplicar / desfazer
def _same(cur, want) -> bool:
    if cur is None:
        return False
    data = cur[1]
    if isinstance(want, int) and not isinstance(want, bool):
        try:
            return int(data) == want
        except (TypeError, ValueError):
            return False
    return str(data) == str(want)


def is_applied(store, tweak: Tweak) -> bool:
    return all(_same(store.get(v.hive, v.key, v.name), v.on) for v in tweak.values)


def _encode(cur):
    if cur is None:
        return None
    kind, data = cur
    if isinstance(data, (bytes, bytearray)):
        return [kind, data.hex(), "hex"]
    return [kind, data]


def _decode(entry):
    if entry is None:
        return None, None
    kind, data = entry[0], entry[1]
    if len(entry) > 2 and entry[2] == "hex":
        data = bytes.fromhex(data)
    return kind, data


def apply_tweak(store, tweak: Tweak, backup: dict) -> None:
    """Guarda os valores originais (só na primeira vez) e grava os novos."""
    if tweak.id not in backup:
        backup[tweak.id] = [[v.hive, v.key, v.name, _encode(store.get(v.hive, v.key, v.name))]
                            for v in tweak.values]
    ops = [(v.hive, v.key, v.name, v.kind, v.on) for v in tweak.values]
    store.write_many(ops)
    log(f"AJUSTE APLICADO {tweak.title}")


def undo_tweak(store, tweak: Tweak, backup: dict) -> None:
    """Restaura os valores originais (ou o padrão do Windows, se não há backup)."""
    saved = {(h, k.lower(), n): enc for h, k, n, enc in backup.get(tweak.id, [])}
    ops = []
    for v in tweak.values:
        key = (v.hive, v.key.lower(), v.name)
        if key in saved:
            kind, data = _decode(saved[key])
        elif v.default is None:
            kind, data = None, None
        else:
            kind, data = v.kind, v.default
        ops.append((v.hive, v.key, v.name, kind, data))
    store.write_many(ops)
    backup.pop(tweak.id, None)
    log(f"AJUSTE DESFEITO {tweak.title}")


# =================================================================== plano de energia
POWER_PLANS = {
    "balanced": ("381b4222-f694-41f0-9685-ff5bb260df2e", "Equilibrado"),
    "high": ("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "Alto desempenho"),
    "ultimate": ("e9a42b02-d5df-448d-aa00-03f14749eb61", "Desempenho máximo"),
    "saver": ("a1841308-3541-4fab-bc81-f71556f20b4a", "Economia de energia"),
}
_GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _powercfg(*args, timeout=30):
    try:
        r = subprocess.run(["powercfg", *args], capture_output=True, creationflags=NO_WINDOW, timeout=timeout)
        raw = r.stdout or b""
        try:
            out = raw.decode("utf-8")
        except UnicodeDecodeError:
            out = raw.decode("oem" if IS_WIN else "latin-1", "replace")   # console usa a página OEM
        return r.returncode, out
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def parse_power_list(text: str) -> tuple[list[tuple[str, str]], str | None]:
    """Lê a saída de `powercfg /list` (qualquer idioma): ([(guid, nome)], guid_ativo)."""
    plans, active = [], None
    for line in (text or "").splitlines():
        m = _GUID.search(line)
        if not m:
            continue
        guid = m.group(0).lower()
        name_m = re.search(r"\((.*?)\)", line[m.end():])
        name = name_m.group(1) if name_m else guid
        plans.append((guid, name))
        if line.rstrip().endswith("*"):
            active = guid
    return plans, active


def power_status(settings) -> dict:
    """{'active': chave conhecida ou None, 'active_name': str, 'plans': [...]}"""
    if not IS_WIN:
        return {"active": None, "active_name": "", "plans": []}
    _, out = _powercfg("/list")
    plans, active = parse_power_list(out)
    known = dict(settings.get("power_plans") or {})
    key = None
    for k, (guid, _) in POWER_PLANS.items():
        if active in (guid, known.get(k)):
            key = k
    name = next((n for g, n in plans if g == active), "")
    return {"active": key, "active_name": name, "plans": plans}


def set_power_plan(kind: str, settings) -> str:
    """Ativa o plano. Cria uma cópia do plano escondido (Alto desempenho / Desempenho máximo) quando
    ele não existe neste PC. Retorna o nome do plano ativado."""
    if not IS_WIN:
        raise RuntimeError("disponível apenas no Windows")
    guid, label = POWER_PLANS[kind]
    _, out = _powercfg("/list")
    plans, _ = parse_power_list(out)
    existing = {g for g, _ in plans}
    known = dict(settings.get("power_plans") or {})
    target = guid if guid in existing else known.get(kind) if known.get(kind) in existing else None
    if not target:
        rc, out = _powercfg("-duplicatescheme", guid)
        m = _GUID.findall(out or "")
        new = [g.lower() for g in m if g.lower() != guid]
        if rc != 0 or not new:
            raise RuntimeError(f"O plano “{label}” não está disponível neste computador "
                               "(alguns notebooks com “Modern Standby” não permitem).")
        target = new[0]
        known[kind] = target
        settings["power_plans"] = known
        if hasattr(settings, "save"):
            settings.save()
    rc, out = _powercfg("/setactive", target)
    if rc != 0:
        raise RuntimeError(out.strip() or "não foi possível ativar o plano de energia")
    log(f"PLANO DE ENERGIA {label}")
    return label


def restart_explorer() -> None:
    if not IS_WIN:
        raise RuntimeError("disponível apenas no Windows")
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True, creationflags=NO_WINDOW)
    exe = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "explorer.exe")
    subprocess.Popen([exe], close_fds=True)
    log("EXPLORER REINICIADO")
