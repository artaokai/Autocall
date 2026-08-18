import os
import sys
import subprocess
import threading
import queue
import time
import shutil
import re
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import winreg
except ImportError:
    winreg = None


# ============================== LISENSI & API KONFIGURASI ==============================

API_BASE_URL = "https://artatools.vercel.app"
SECRET_KEY = "rc1cP5vA4BiEKlVgdj1oEuY33CBS1i7OllXTBD5DWJQ="
LICENSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "license_config.json")


def load_saved_license_key():
    if os.path.isfile(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("license_key", "")
        except Exception:
            pass
    return ""


def save_license_key(key):
    try:
        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump({"license_key": key}, f)
    except Exception:
        pass


def check_arta_license(license_key):
    """
    Fungsi untuk mengecek status lisensi ke server ArtaTools.
    Hanya mengizinkan akses untuk user dengan tier 'premium'.
    """
    import urllib.request
    import urllib.parse
    import urllib.error

    endpoint = f"{API_BASE_URL}/api/v1/license/check"
    params = {"key": license_key}
    query_string = urllib.parse.urlencode(params)
    url = f"{endpoint}?{query_string}"
    
    req = urllib.request.Request(url, headers={"X-Arta-Secret": SECRET_KEY})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            response_data = response.read().decode('utf-8')
            
            if status_code == 200:
                result = json.loads(response_data)
                if result.get("success"):
                    data = result.get("data")
                    if not data.get("is_active"):
                        return False, "Lisensi Anda sudah kadaluwarsa (Expired) atau Dinonaktifkan."
                    
                    tier = str(data.get("tier", "")).lower().strip()
                    if tier != "premium":
                        return False, f"Akses Ditolak: Aplikasi ini khusus untuk User PREMIUM (Tier Anda: {tier.upper() or 'FREE'})."
                    
                    return True, data
                else:
                    return False, result.get("message", "Validasi gagal.")
            else:
                return False, f"Server Error (Status: {status_code})"

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Aplikasi ini tidak memiliki otorisasi sah (Invalid Secret Key)."
        elif e.code == 404:
            return False, "Kunci Lisensi tidak ditemukan di database."
        else:
            return False, f"Server Error (Status: {e.code})"
    except urllib.error.URLError as e:
        return False, f"Gagal terhubung ke server validasi: {str(e.reason)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============================== LOGIKA INTI ==============================

def find_all_microsip_candidates():
    """
    Kumpulkan instansi MicroSIP.
    Prioritaskan instansi khusus di C:\\ArtCaller\\ (SIP1, SIP2, dst).
    Jika C:\\ArtCaller\\ memiliki instansi, HANYA kembalikan instansi dari C:\\ArtCaller\\
    agar tidak ada bentrokan dengan MicroSIP terinstall di Program Files / AppData.
    """
    artcaller_candidates = []
    artcaller_dir = r"C:\ArtCaller"
    if os.path.isdir(artcaller_dir):
        try:
            for item in os.listdir(artcaller_dir):
                sub_dir = os.path.join(artcaller_dir, item)
                if os.path.isdir(sub_dir):
                    for sub_item in os.listdir(sub_dir):
                        if sub_item.lower().endswith(".exe") and "microsip" in sub_item.lower():
                            exe_p = os.path.normpath(os.path.join(sub_dir, sub_item))
                            if exe_p not in artcaller_candidates:
                                artcaller_candidates.append(exe_p)
        except Exception:
            pass

    # Jika sudah ada instansi khusus di C:\ArtCaller\, HANYA gunakan instansi C:\ArtCaller\!
    if artcaller_candidates:
        def sort_key(path):
            match = re.search(r'[S|s][I|i][P|p](\d+)', path)
            if match:
                return (0, int(match.group(1)))
            return (1, path)
        artcaller_candidates.sort(key=sort_key)
        return artcaller_candidates

    # Jika C:\ArtCaller\ belum ada instansi, cari master candidate dari sistem (Program Files / AppData)
    other_candidates = []
    env_vars = ["LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "APPDATA", "USERPROFILE"]
    for var in env_vars:
        base = os.environ.get(var)
        if base:
            other_candidates.append(os.path.join(base, "MicroSIP", "microsip.exe"))
            other_candidates.append(os.path.join(base, "MicroSIP", "MicroSIP.exe"))

    other_candidates.append(r"C:\Program Files\MicroSIP\microsip.exe")
    other_candidates.append(r"C:\Program Files (x86)\MicroSIP\microsip.exe")
    other_candidates.append(r"C:\MicroSIP\microsip.exe")

    seen = set()
    unique = []
    for c in other_candidates:
        if os.path.isfile(c):
            c_norm = os.path.normpath(c)
            if c_norm not in seen:
                seen.add(c_norm)
                unique.append(c_norm)
    return unique


def duplicate_microsip_instance(source_exe_path, target_root=r"C:\ArtCaller"):
    r"""
    Menduplikasi folder MicroSIP sumber ke C:\ArtCaller\SIP<N>\MicroSIP.exe
    """
    if not source_exe_path or not os.path.isfile(source_exe_path):
        raise FileNotFoundError("File microsip.exe sumber tidak ditemukan.")

    source_dir = os.path.dirname(source_exe_path)
    os.makedirs(target_root, exist_ok=True)

    n = 1
    while True:
        target_dir = os.path.join(target_root, f"SIP{n}")
        if not os.path.exists(target_dir):
            break
        n += 1

    target_dir = os.path.join(target_root, f"SIP{n}")
    os.makedirs(target_dir, exist_ok=True)

    if os.path.isdir(source_dir):
        for item in os.listdir(source_dir):
            s = os.path.join(source_dir, item)
            d = os.path.join(target_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

    target_exe_path = os.path.join(target_dir, "MicroSIP.exe")
    source_exe_name = os.path.basename(source_exe_path)
    copied_source_exe = os.path.join(target_dir, source_exe_name)

    if not os.path.isfile(target_exe_path):
        if os.path.isfile(copied_source_exe):
            shutil.copy2(copied_source_exe, target_exe_path)
        else:
            shutil.copy2(source_exe_path, target_exe_path)

    return target_exe_path


# ============================== MANAGEMENT AKUN SIP INI ==============================

def read_microsip_account(instance_exe_path):
    """Membaca informasi [Account1] dari file MicroSIP.ini instansi."""
    dir_path = os.path.dirname(instance_exe_path)
    ini_candidates = [
        os.path.join(dir_path, "MicroSIP.ini"),
        os.path.join(dir_path, "microsip.ini"),
    ]
    
    appdata = os.environ.get("APPDATA")
    if appdata:
        ini_candidates.append(os.path.join(appdata, "MicroSIP", "MicroSIP.ini"))

    account_info = {
        "server": "",
        "domain": "",
        "username": "",
        "password": "",
        "displayname": "",
        "label": "",
    }

    for ini_p in ini_candidates:
        if os.path.isfile(ini_p):
            try:
                content = ""
                for enc in ["utf-8", "utf-16", "latin-1"]:
                    try:
                        with open(ini_p, "r", encoding=enc) as f:
                            content = f.read()
                        if content:
                            break
                    except Exception:
                        pass

                in_account1 = False
                for line in content.splitlines():
                    line_str = line.strip()
                    if line_str.lower() == "[account1]":
                        in_account1 = True
                        continue
                    elif line_str.startswith("[") and line_str.endswith("]"):
                        in_account1 = False
                        continue
                    
                    if in_account1 and "=" in line_str:
                        key, val = line_str.split("=", 1)
                        key = key.strip().lower()
                        val = val.strip()
                        if key in account_info:
                            account_info[key] = val
                
                if account_info["server"] or account_info["username"]:
                    break
            except Exception:
                pass

    return account_info


def save_microsip_account(instance_exe_path, server, username, password, domain="", displayname="", label=""):
    """Menulis/Memperbarui file MicroSIP.ini & microsip.ini instansi dengan UTF-8 CRLF (Portable Mode)."""
    dir_path = os.path.dirname(instance_exe_path)
    ini_path = os.path.join(dir_path, "MicroSIP.ini")
    ini_lower_path = os.path.join(dir_path, "microsip.ini")
    
    if not domain:
        domain = server

    lines = [
        "[Global]",
        "version=3.22.12",
        "",
        "[Settings]",
        "accountId=1",
        "singleMode=1",
        "",
        "[Account1]",
        f"label={label or username}",
        f"server={server}",
        f"domain={domain}",
        f"username={username}",
        f"authuser={username}",
        f"password={password}",
        f"displayname={displayname or username}",
        "register=1",
        "pubAddr=",
        "srtp=",
        "transport=auto",
        ""
    ]

    # Windows CRLF line endings in UTF-8 encoding (MicroSIP Portable standard)
    content_str = "\r\n".join(lines)
    
    for target in [ini_path, ini_lower_path]:
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(content_str)
        except Exception:
            pass


def run_calls(microsip_paths, numbers, dial_wait, hangup_wait, recall_count, log_queue, stop_event):
    """
    Jalankan panggilan secara paralel bersamaan (Parallel Batch Call).
    Mendukung fitur Recall (pengulangan sesi panggilan).
    recall_count: 1 = 1x putaran, N = Nx putaran, 0 = tak terbatas (infinite).
    """
    total = len(numbers)
    num_instances = len(microsip_paths)

    if num_instances == 0 or total == 0:
        log_queue.put(("done", "Tidak ada instansi atau nomor yang dipanggil."))
        return

    loop_idx = 1
    while not stop_event.is_set():
        if recall_count > 0 and loop_idx > recall_count:
            break

        if recall_count > 1 or recall_count == 0:
            log_queue.put(("info", f"========== Putaran Panggilan #{loop_idx} (Recall) =========="))
        else:
            log_queue.put(("info", f"========== Putaran Panggilan #{loop_idx} =========="))

        i = 0
        batch_num = 1
        while i < total and not stop_event.is_set():
            chunk = numbers[i : i + num_instances]
            current_batch_paths = microsip_paths[: len(chunk)]

            log_queue.put(("info", f"--- Putaran #{loop_idx} - Batch {batch_num} ({len(chunk)} Panggilan Serentak) ---"))

            # 1. Panggil semua nomor dalam batch secara bersamaan (parallel)
            active_calls = []
            for j, number in enumerate(chunk):
                if stop_event.is_set():
                    break
                current_path = current_batch_paths[j]
                inst_dir = os.path.dirname(current_path)
                folder_name = os.path.basename(inst_dir)
                global_idx = i + j + 1
                log_queue.put(("call", f"[P#{loop_idx}] [{global_idx}/{total}] [{folder_name}] Menelepon {number} ..."))
                try:
                    # Set cwd=inst_dir agar MicroSIP membaca MicroSIP.ini di foldernya sendiri (Portable Mode)
                    subprocess.Popen([current_path, number], cwd=inst_dir)
                    active_calls.append((current_path, number, folder_name, inst_dir))
                except Exception as e:
                    log_queue.put(("error", f"[{folder_name}] Gagal memanggil {number}: {e}"))

            if stop_event.is_set():
                log_queue.put(("info", "Dihentikan oleh pengguna."))
                break

            # 2. Tunggu durasi panggilan (dial_wait)
            waited = 0.0
            while waited < dial_wait and not stop_event.is_set():
                time.sleep(0.2)
                waited += 0.2

            # 3. Hangup semua instansi dalam batch yang telah memanggil
            for current_path, number, folder_name, inst_dir in active_calls:
                try:
                    subprocess.run([current_path, "/hangupall"], cwd=inst_dir)
                except Exception as e:
                    log_queue.put(("error", f"[{folder_name}] Gagal hangup: {e}"))

            log_queue.put(("info", f"Putaran #{loop_idx} - Batch {batch_num} selesai."))

            if stop_event.is_set():
                log_queue.put(("info", "Dihentikan oleh pengguna."))
                break

            # 4. Jeda antar batch (hangup_wait)
            waited = 0.0
            while waited < hangup_wait and not stop_event.is_set():
                time.sleep(0.2)
                waited += 0.2

            i += num_instances
            batch_num += 1

        loop_idx += 1

    if not stop_event.is_set():
        log_queue.put(("done", f"Proses Selesai. Seluruh putaran ({loop_idx - 1}x) telah dilaksanakan."))


# ============================== ANTARMUKA (GUI) MODERN ==============================

BG = "#0f172a"          # Slate 900
BG_PANEL = "#1e293b"    # Slate 800
BG_CARD = "#334155"     # Slate 700
BG_INPUT = "#0b0f19"    # Dark input background
FG = "#f8fafc"          # Slate 50
MUTED = "#94a3b8"       # Slate 400
ACCENT = "#6366f1"      # Indigo 500
ACCENT_HOVER = "#4f46e5" # Indigo 600
SUCCESS = "#10b981"     # Emerald 500
DANGER = "#f43f5e"      # Rose 500
DANGER_HOVER = "#e11d48"

FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_SUBTITLE = ("Segoe UI", 9)
FONT_HEADING = ("Segoe UI", 11, "bold")
FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 10)
FONT_STAT = ("Segoe UI", 16, "bold")


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, frame_kwargs=None, bg_color=None, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        if frame_kwargs is None:
            frame_kwargs = {}
        if bg_color is None:
            bg_color = BG

        self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, **frame_kwargs)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        try:
            x, y = self.winfo_pointerxy()
            widget_under_mouse = self.winfo_containing(x, y)
            
            if not widget_under_mouse:
                return
                
            parent = widget_under_mouse
            is_inside = False
            while parent:
                if parent == self:
                    is_inside = True
                    break
                parent = parent.master
                
            if not is_inside:
                return
                
            widget_class = widget_under_mouse.winfo_class() if hasattr(widget_under_mouse, 'winfo_class') else ''
            if widget_class in ('Text', 'Treeview'):
                return
                
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except Exception:
            pass


class BatchAccountDialog(tk.Toplevel):
    """
    Modal Dialog modern untuk input massal (Batch) Username & Password SIP.
    """
    def __init__(self, parent, source_path):
        super().__init__(parent)
        self.source_path = source_path
        self.title("⚡ Batch Add Akun SIP")
        self.geometry("680x520")
        self.minsize(600, 440)
        self.configure(bg=BG_PANEL)
        self.transient(parent)
        self.grab_set()
        self.created_paths = []
        self._build_ui()

    def _build_ui(self):
        sf = ScrollableFrame(self, frame_kwargs={"padding": 20, "style": "Panel.TFrame"}, bg_color=BG_PANEL)
        sf.pack(fill="both", expand=True)
        root_frame = sf.scrollable_frame

        # Header Title
        ttk.Label(root_frame, text="⚡ Batch Input Akun SIP", style="PanelHeading.TLabel").pack(anchor="w")
        ttk.Label(root_frame,
                  text="Masukkan username di kolom kiri & password di kolom kanan (1 per baris).\n"
                       "Sistem akan otomatis memasangkan baris ke-N username dengan baris ke-N password.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        # SIP Server & Domain row
        sf = ttk.Frame(root_frame, style="Panel.TFrame")
        sf.pack(fill="x", pady=(0, 12))

        ttk.Label(sf, text="SIP Server:", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        self.server_var = tk.StringVar(value="agent.vocallink.ai:6060")
        ttk.Entry(sf, textvariable=self.server_var, font=FONT_UI).grid(
            row=0, column=1, sticky="ew", padx=(8, 16))

        ttk.Label(sf, text="Domain/Proxy:", style="Panel.TLabel").grid(row=0, column=2, sticky="w")
        self.domain_var = tk.StringVar()
        ttk.Entry(sf, textvariable=self.domain_var, font=FONT_UI).grid(
            row=0, column=3, sticky="ew", padx=(8, 0))

        sf.columnconfigure(1, weight=1)
        sf.columnconfigure(3, weight=1)

        # Pinned Bottom Buttons (so they are NEVER cut off)
        btn_box = ttk.Frame(root_frame, style="Panel.TFrame")
        btn_box.pack(side="bottom", fill="x", pady=(12, 0))

        self.count_badge_var = tk.StringVar(value="0 Akun Siap Dibuat")
        ttk.Label(btn_box, textvariable=self.count_badge_var, style="Muted.TLabel").pack(side="left", anchor="c")

        ttk.Button(btn_box, text="⚡ Buat Semua Instansi SIP", style="Accent.TButton",
                   command=self._generate_clicked).pack(side="right")
        ttk.Button(btn_box, text="Batal", style="Secondary.TButton",
                   command=self.destroy).pack(side="right", padx=(0, 8))

        # Dual Text Area Container
        dual = ttk.Frame(root_frame, style="Panel.TFrame")
        dual.pack(side="top", fill="both", expand=True)
        dual.columnconfigure(0, weight=1)
        dual.columnconfigure(1, weight=1)
        dual.rowconfigure(1, weight=1)

        # Column Headers
        ttk.Label(dual, text="Username / Ekstensi", style="PanelHeading.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 4), pady=(0, 4))
        ttk.Label(dual, text="Password SIP", style="PanelHeading.TLabel").grid(
            row=0, column=1, sticky="w", padx=(4, 0), pady=(0, 4))

        # Username textarea
        self.user_text = tk.Text(
            dual, bg=BG_INPUT, fg=FG, insertbackground=FG,
            font=FONT_MONO, relief="flat", padx=10, pady=8, wrap="none", height=10)
        self.user_text.grid(row=1, column=0, sticky="nsew", padx=(0, 4))

        # Password textarea
        self.pass_text = tk.Text(
            dual, bg=BG_INPUT, fg=FG, insertbackground=FG,
            font=FONT_MONO, relief="flat", padx=10, pady=8, wrap="none", height=10)
        self.pass_text.grid(row=1, column=1, sticky="nsew", padx=(4, 0))

        # Bind KeyRelease to update count badge
        self.user_text.bind("<KeyRelease>", self._update_count)
        self.pass_text.bind("<KeyRelease>", self._update_count)

    def _update_count(self, event=None):
        usernames = [u.strip() for u in self.user_text.get("1.0", "end").splitlines() if u.strip()]
        self.count_badge_var.set(f"{len(usernames)} Akun Terdeteksi")

    def _generate_clicked(self):
        server = self.server_var.get().strip()
        domain = self.domain_var.get().strip() or server

        if not server:
            messagebox.showerror("Input Kosong", "SIP Server wajib diisi.", parent=self)
            return

        usernames = [u.strip() for u in self.user_text.get("1.0", "end").splitlines() if u.strip()]
        passwords = [p.strip() for p in self.pass_text.get("1.0", "end").splitlines() if p.strip()]

        if not usernames:
            messagebox.showerror("Kolom Kosong", "Isi minimal satu username.", parent=self)
            return

        pairs = [(usernames[i], passwords[i] if i < len(passwords) else "") for i in range(len(usernames))]

        created = []
        for u, p in pairs:
            new_exe = duplicate_microsip_instance(self.source_path)
            save_microsip_account(new_exe, server=server, username=u, password=p, domain=domain, label=u)
            created.append(new_exe)

        self.created_paths = created
        messagebox.showinfo(
            "Batch Create Berhasil!",
            f"Berhasil membuat {len(created)} instansi MicroSIP!\nStruktur: C:\\ArtCaller\\SIP<N>\\MicroSIP.exe",
            parent=self)
        self.destroy()


class SingleAccountDialog(tk.Toplevel):
    """Modal Dialog modern untuk Setup 1 Akun SIP."""
    def __init__(self, parent, instance_exe_path):
        super().__init__(parent)
        self.instance_exe_path = instance_exe_path
        self.title("⚙️ Setup Akun SIP MicroSIP")
        self.geometry("480x420")
        self.resizable(False, False)
        self.configure(bg=BG_PANEL)
        self.transient(parent)
        self.grab_set()

        self.account_data = read_microsip_account(instance_exe_path)
        self._build_ui()

    def _build_ui(self):
        sf = ScrollableFrame(self, frame_kwargs={"padding": 20, "style": "Panel.TFrame"}, bg_color=BG_PANEL)
        sf.pack(fill="both", expand=True)
        container = sf.scrollable_frame

        ttk.Label(container, text="Pengaturan Akun SIP", style="PanelHeading.TLabel").pack(anchor="w")
        inst_name = os.path.basename(os.path.dirname(self.instance_exe_path))
        ttk.Label(container, text=f"Instansi: {inst_name}\\MicroSIP.exe", style="Muted.TLabel").pack(anchor="w", pady=(0, 14))

        form_frame = ttk.Frame(container, style="Panel.TFrame")
        form_frame.pack(fill="x", pady=(0, 14))

        ttk.Label(form_frame, text="SIP Server (IP:Port):", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        self.server_var = tk.StringVar(value=self.account_data.get("server", ""))
        ttk.Entry(form_frame, textvariable=self.server_var, font=FONT_UI).grid(row=0, column=1, sticky="ew", pady=6, padx=(10, 0))

        ttk.Label(form_frame, text="Domain / Proxy (opsional):", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        self.domain_var = tk.StringVar(value=self.account_data.get("domain", ""))
        ttk.Entry(form_frame, textvariable=self.domain_var, font=FONT_UI).grid(row=1, column=1, sticky="ew", pady=6, padx=(10, 0))

        ttk.Label(form_frame, text="Username / Ekstensi:", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        self.username_var = tk.StringVar(value=self.account_data.get("username", ""))
        ttk.Entry(form_frame, textvariable=self.username_var, font=FONT_UI).grid(row=2, column=1, sticky="ew", pady=6, padx=(10, 0))

        ttk.Label(form_frame, text="Password SIP:", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=6)
        self.password_var = tk.StringVar(value=self.account_data.get("password", ""))
        ttk.Entry(form_frame, textvariable=self.password_var, font=FONT_UI, show="*").grid(row=3, column=1, sticky="ew", pady=6, padx=(10, 0))

        ttk.Label(form_frame, text="Display Name / Label:", style="Panel.TLabel").grid(row=4, column=0, sticky="w", pady=6)
        self.display_var = tk.StringVar(value=self.account_data.get("displayname", ""))
        ttk.Entry(form_frame, textvariable=self.display_var, font=FONT_UI).grid(row=4, column=1, sticky="ew", pady=6, padx=(10, 0))

        form_frame.columnconfigure(1, weight=1)

        btn_box = ttk.Frame(container, style="Panel.TFrame")
        btn_box.pack(fill="x", side="bottom")

        ttk.Button(btn_box, text="Simpan Akun SIP", style="Accent.TButton", command=self._save_clicked).pack(side="right")
        ttk.Button(btn_box, text="Batal", style="Secondary.TButton", command=self.destroy).pack(side="right", padx=(0, 8))

    def _save_clicked(self):
        server = self.server_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        domain = self.domain_var.get().strip()
        displayname = self.display_var.get().strip()

        if not server or not username or not password:
            messagebox.showerror("Input Belum Lengkap", "SIP Server, Username, dan Password wajib diisi.", parent=self)
            return

        try:
            save_microsip_account(self.instance_exe_path, server=server, username=username, password=password,
                                  domain=domain, displayname=displayname, label=displayname or username)
            messagebox.showinfo("Berhasil Disimpan", f"Akun SIP ({username}@{server}) telah disimpan!", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Gagal Menyimpan", f"Terjadi kesalahan: {e}", parent=self)


class LicenseLoginWindow:
    """Tampilan GUI Login / Validasi Lisensi ArtaTools."""
    def __init__(self, root):
        self.root = root
        self.root.title("🔑 Otorisasi Lisensi — ARTA TOOLS PREMIUM ENGINE")
        self.root.geometry("540x440")
        self.root.minsize(500, 400)
        self.root.configure(bg=BG)

        self._build_style()
        self._build_ui()

        # Load saved key and auto-check if available
        saved_key = load_saved_license_key()
        if saved_key:
            self.key_var.set(saved_key)
            self.root.after(300, self._start_validation_thread)

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("TLabel", background=BG, foreground=FG, font=FONT_UI)
        style.configure("Muted.TLabel", background=BG_PANEL, foreground=MUTED, font=FONT_SUBTITLE)
        style.configure("PanelHeading.TLabel", background=BG_PANEL, foreground=FG, font=FONT_HEADING)
        style.configure("HeaderTitle.TLabel", background=BG, foreground=FG, font=FONT_TITLE)
        style.configure("HeaderSub.TLabel", background=BG, foreground=MUTED, font=FONT_SUBTITLE)

        style.configure("Accent.TButton", background=ACCENT, foreground="white",
                        font=FONT_UI_BOLD, padding=(14, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#374151")])

    def _build_ui(self):
        sf = ScrollableFrame(self.root, frame_kwargs={"padding": 24}, bg_color=BG)
        sf.pack(fill="both", expand=True)
        main_container = sf.scrollable_frame

        # Header Title
        header = ttk.Frame(main_container)
        header.pack(fill="x", pady=(0, 20))

        ttk.Label(header, text="🔑 ARTA TOOLS PREMIUM ENGINE", style="HeaderTitle.TLabel").pack(anchor="center")
        ttk.Label(header, text="v1.0 — Sistem Verifikasi & Otorisasi Lisensi Resmi", style="HeaderSub.TLabel").pack(anchor="center", pady=(4, 0))

        # Panel Card Login
        panel = ttk.Frame(main_container, style="Panel.TFrame", padding=20)
        panel.pack(fill="both", expand=True)

        ttk.Label(panel, text="Masukkan Key Lisensi Anda:", style="PanelHeading.TLabel").pack(anchor="w", pady=(0, 8))

        self.key_var = tk.StringVar()
        self.key_entry = ttk.Entry(panel, textvariable=self.key_var, font=("Consolas", 11))
        self.key_entry.pack(fill="x", pady=(0, 14))
        self.key_entry.focus()

        # Status / Feedback Message Label
        self.status_var = tk.StringVar(value="Masukkan License Key dan klik Verifikasi.")
        self.status_label = tk.Label(
            panel, textvariable=self.status_var, bg=BG_PANEL, fg=MUTED,
            font=FONT_SUBTITLE, wraplength=440, justify="center"
        )
        self.status_label.pack(fill="x", pady=(0, 14))

        # Action Buttons
        btn_box = ttk.Frame(panel, style="Panel.TFrame")
        btn_box.pack(fill="x")

        self.verify_btn = ttk.Button(
            btn_box, text="⚡ VERIFIKASI & MASUK APLIKASI", style="Accent.TButton",
            command=self._start_validation_thread
        )
        self.verify_btn.pack(fill="x")

    def _start_validation_thread(self):
        user_key = self.key_var.get().strip()
        if not user_key:
            self.status_var.set("[!] License Key tidak boleh kosong.")
            self.status_label.configure(fg=DANGER)
            return

        self.verify_btn.configure(state="disabled")
        self.status_var.set("[*] Menghubungkan ke server untuk validasi lisensi...")
        self.status_label.configure(fg="#38bdf8")

        threading.Thread(target=self._validate_proc, args=(user_key,), daemon=True).start()

    def _validate_proc(self, user_key):
        is_valid, response_data = check_arta_license(user_key)
        self.root.after(0, lambda: self._on_validation_result(is_valid, response_data, user_key))

    def _on_validation_result(self, is_valid, response_data, user_key):
        self.verify_btn.configure(state="normal")
        if is_valid:
            save_license_key(user_key)
            owner = response_data.get("owner", "User")
            tier = response_data.get("tier", "Premium").upper()
            expires = response_data.get("expires_at") or "Seumur Hidup"

            self.status_var.set(f"[+] LISENSI TERVERIFIKASI!\nPemilik: {owner} | Tier: {tier}\nBerlaku: {expires}")
            self.status_label.configure(fg=SUCCESS)
            
            # Transition to Main Application after brief delay
            self.root.after(800, lambda: self._launch_main_app(response_data))
        else:
            self.status_var.set(f"[!] AKSES DITOLAK: {response_data}")
            self.status_label.configure(fg=DANGER)

    def _launch_main_app(self, response_data):
        for widget in self.root.winfo_children():
            widget.destroy()
        app = ArtCallerApp(self.root, license_data=response_data)


class ArtCallerApp:
    def __init__(self, root, license_data=None):
        self.root = root
        self.license_data = license_data or {}
        self.root.title("Art Caller — Multi-MicroSIP Auto Call")
        self.root.geometry("920x760")
        self.root.minsize(840, 660)
        self.root.configure(bg=BG)

        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.microsip_list = []

        self._build_style()
        self._build_ui()
        self._auto_detect_on_start()
        self._poll_log_queue()

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("Card.TFrame", background=BG_CARD)

        style.configure("TLabel", background=BG, foreground=FG, font=FONT_UI)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_SUBTITLE)
        style.configure("Panel.TLabel", background=BG_PANEL, foreground=FG, font=FONT_UI)
        style.configure("PanelHeading.TLabel", background=BG_PANEL, foreground=FG, font=FONT_HEADING)
        style.configure("HeaderTitle.TLabel", background=BG, foreground=FG, font=FONT_TITLE)
        style.configure("HeaderSub.TLabel", background=BG, foreground=MUTED, font=FONT_SUBTITLE)

        style.configure("CardLabel.TLabel", background=BG_CARD, foreground=MUTED, font=FONT_SUBTITLE)
        style.configure("CardVal.TLabel", background=BG_CARD, foreground=FG, font=FONT_STAT)

        style.configure("TEntry", fieldbackground=BG_INPUT, foreground=FG, insertcolor=FG, borderwidth=0)
        style.configure("TSpinbox", fieldbackground=BG_INPUT, foreground=FG, arrowsize=14)

        style.configure("Accent.TButton", background=ACCENT, foreground="white",
                        font=FONT_UI_BOLD, padding=(14, 7), borderwidth=0)
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#374151")])

        style.configure("Danger.TButton", background=DANGER, foreground="white",
                        font=FONT_UI_BOLD, padding=(14, 7), borderwidth=0)
        style.map("Danger.TButton", background=[("active", DANGER_HOVER), ("disabled", "#374151")])

        style.configure("Secondary.TButton", background="#334155", foreground=FG,
                        font=FONT_UI, padding=(10, 5), borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#475569")])

        style.configure("Horizontal.TProgressbar", troughcolor=BG_PANEL, background=ACCENT,
                        borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)

        style.configure("TCheckbutton", background=BG_PANEL, foreground=FG, font=FONT_UI_BOLD)
        style.map("TCheckbutton", background=[("active", BG_PANEL)], foreground=[("active", ACCENT)])

        # Treeview Styling (Modern Table)
        style.configure("Treeview",
                        background=BG_INPUT,
                        foreground=FG,
                        fieldbackground=BG_INPUT,
                        rowheight=30,
                        font=FONT_UI,
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background=BG_PANEL,
                        foreground=FG,
                        font=FONT_UI_BOLD,
                        padding=(6, 6))
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])

    def _build_ui(self):
        sf = ScrollableFrame(self.root, frame_kwargs={"padding": 20}, bg_color=BG)
        sf.pack(fill="both", expand=True)
        main_container = sf.scrollable_frame

        # 1. Header Row
        header = ttk.Frame(main_container)
        header.pack(fill="x", pady=(0, 16))

        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        ttk.Label(title_box, text="Art Caller", style="HeaderTitle.TLabel").pack(anchor="w")
        
        owner = self.license_data.get("owner", "")
        tier = self.license_data.get("tier", "").upper()
        lic_suffix = f" — Lic: {owner} [{tier}]" if owner else ""
        sub_title_txt = f"Sistem Multi-MicroSIP Auto Call (Parallel Batch Call){lic_suffix}"
        ttk.Label(title_box, text=sub_title_txt, style="HeaderSub.TLabel").pack(anchor="w")

        # Status Badge
        self.status_badge_var = tk.StringVar(value=" READY ")
        self.status_label = tk.Label(header, textvariable=self.status_badge_var,
                                     bg=SUCCESS, fg="#ffffff", font=("Segoe UI", 9, "bold"),
                                     padx=14, pady=4)
        self.status_label.pack(side="right", anchor="c")

        # 2. Multi-MicroSIP Management Panel with Modern Treeview Table
        path_panel = ttk.Frame(main_container, style="Panel.TFrame", padding=14)
        path_panel.pack(fill="both", expand=True, pady=(0, 12))

        panel_top = ttk.Frame(path_panel, style="Panel.TFrame")
        panel_top.pack(fill="x", pady=(0, 8))
        ttk.Label(panel_top, text="Daftar Instansi MicroSIP & Akun SIP", style="PanelHeading.TLabel").pack(side="left")

        self.instance_count_var = tk.StringVar(value="0 Instansi Terdaftar")
        ttk.Label(panel_top, textvariable=self.instance_count_var, style="Muted.TLabel").pack(side="right")

        # Treeview Table replacing old listbox
        tree_frame = ttk.Frame(path_panel, style="Panel.TFrame")
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))

        columns = ("num", "path", "user", "server", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=5)
        
        self.tree.heading("num", text="#")
        self.tree.heading("path", text="Executable / Folder Instansi")
        self.tree.heading("user", text="Username SIP")
        self.tree.heading("server", text="SIP Server")
        self.tree.heading("status", text="Status INI")

        self.tree.column("num", width=40, anchor="center", stretch=False)
        self.tree.column("path", width=340, anchor="w", stretch=True)
        self.tree.column("user", width=140, anchor="w", stretch=True)
        self.tree.column("server", width=180, anchor="w", stretch=True)
        self.tree.column("status", width=100, anchor="center", stretch=False)

        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=scrollbar.set)

        # Control buttons row
        btn_row = ttk.Frame(path_panel, style="Panel.TFrame")
        btn_row.pack(fill="x")

        ttk.Button(btn_row, text="⚡ Tabel Batch Input Akun", style="Accent.TButton",
                   command=self._batch_account_clicked).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="⚙️ Edit Akun SIP", style="Secondary.TButton",
                   command=self._setup_account_clicked).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="🔍 Auto-Detect", style="Secondary.TButton",
                   command=self._auto_detect_all_clicked).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="🗑 Hapus Instansi & Folder", style="Danger.TButton",
                   command=self._remove_selected_clicked).pack(side="left")

        # 3. Dashboard Info Cards
        cards_frame = ttk.Frame(main_container)
        cards_frame.pack(fill="x", pady=(0, 12))
        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)
        cards_frame.columnconfigure(2, weight=1)

        c1 = ttk.Frame(cards_frame, style="Card.TFrame", padding=12)
        c1.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Label(c1, text="Status Mode", style="CardLabel.TLabel").pack(anchor="w")
        self.card_mode_var = tk.StringVar(value="Standby")
        ttk.Label(c1, textvariable=self.card_mode_var, style="CardVal.TLabel").pack(anchor="w", pady=(2, 0))

        c2 = ttk.Frame(cards_frame, style="Card.TFrame", padding=12)
        c2.grid(row=0, column=1, sticky="ew", padx=(4, 4))
        ttk.Label(c2, text="Aktif MicroSIP", style="CardLabel.TLabel").pack(anchor="w")
        self.card_inst_var = tk.StringVar(value="0 Instansi")
        ttk.Label(c2, textvariable=self.card_inst_var, style="CardVal.TLabel").pack(anchor="w", pady=(2, 0))

        c3 = ttk.Frame(cards_frame, style="Card.TFrame", padding=12)
        c3.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        ttk.Label(c3, text="Struktur Folder", style="CardLabel.TLabel").pack(anchor="w")
        self.card_rot_var = tk.StringVar(value="C:\\ArtCaller\\SIP<N>\\MicroSIP.exe")
        ttk.Label(c3, textvariable=self.card_rot_var, style="CardVal.TLabel").pack(anchor="w", pady=(2, 0))

        # 4. Panel Input Nomor Tujuan
        phone_panel = ttk.Frame(main_container, style="Panel.TFrame", padding=14)
        phone_panel.pack(fill="x", pady=(0, 12))

        phone_top = ttk.Frame(phone_panel, style="Panel.TFrame")
        phone_top.pack(fill="x", pady=(0, 6))
        ttk.Label(phone_top, text="📞 Daftar Nomor Tujuan (1 Nomor per Baris)", style="PanelHeading.TLabel").pack(side="left")

        self.phone_count_var = tk.StringVar(value="3 Nomor Terdeteksi")
        ttk.Label(phone_top, textvariable=self.phone_count_var, style="Muted.TLabel").pack(side="right")

        phone_frame = ttk.Frame(phone_panel, style="Panel.TFrame")
        phone_frame.pack(fill="x")

        self.phone_text = tk.Text(
            phone_frame, height=4, bg=BG_INPUT, fg=FG, insertbackground=FG,
            font=FONT_MONO, relief="flat", padx=10, pady=8, wrap="none")
        self.phone_text.pack(side="left", fill="x", expand=True)

        phone_scroll = ttk.Scrollbar(phone_frame, orient="vertical", command=self.phone_text.yview)
        phone_scroll.pack(side="right", fill="y")
        self.phone_text.config(yscrollcommand=phone_scroll.set)

        # Default example numbers
        self.phone_text.insert("1.0", "")

        # Bind KeyRelease to update count badge
        self.phone_text.bind("<KeyRelease>", self._update_phone_count)

        # 5. Settings Panel
        settings_panel = ttk.Frame(main_container, style="Panel.TFrame", padding=14)
        settings_panel.pack(fill="x", pady=(0, 12))

        ttk.Label(settings_panel, text="Pengaturan Durasi Panggilan & Jeda", style="PanelHeading.TLabel").pack(anchor="w", pady=(0, 8))

        sett_row = ttk.Frame(settings_panel, style="Panel.TFrame")
        sett_row.pack(fill="x")

        col1 = ttk.Frame(sett_row, style="Panel.TFrame")
        col1.pack(side="left", padx=(0, 40))
        ttk.Label(col1, text="Tunggu Sebelum Hangup (Detik):", style="Panel.TLabel").pack(anchor="w")
        self.dial_wait_var = tk.StringVar(value="20")
        dial_spin = ttk.Spinbox(col1, from_=1, to=120, textvariable=self.dial_wait_var, width=10, font=FONT_UI)
        dial_spin.pack(anchor="w", pady=(4, 0))

        col2 = ttk.Frame(sett_row, style="Panel.TFrame")
        col2.pack(side="left", padx=(0, 40))
        ttk.Label(col2, text="Jeda Antar Panggilan (Detik):", style="Panel.TLabel").pack(anchor="w")
        self.hangup_wait_var = tk.StringVar(value="2")
        delay_spin = ttk.Spinbox(col2, from_=0, to=60, textvariable=self.hangup_wait_var, width=10, font=FONT_UI)
        delay_spin.pack(anchor="w", pady=(4, 0))

        col3 = ttk.Frame(sett_row, style="Panel.TFrame")
        col3.pack(side="left")
        ttk.Label(col3, text="Jumlah Pengulangan (Recall):", style="Panel.TLabel").pack(anchor="w")

        recall_box = ttk.Frame(col3, style="Panel.TFrame")
        recall_box.pack(anchor="w", pady=(4, 0))

        self.recall_var = tk.StringVar(value="1")
        self.recall_spin = ttk.Spinbox(recall_box, from_=1, to=999, textvariable=self.recall_var, width=8, font=FONT_UI)
        self.recall_spin.pack(side="left")

        self.infinity_var = tk.BooleanVar(value=False)
        self.infinity_cb = ttk.Checkbutton(
            recall_box, text="♾️ Infinity Loop", variable=self.infinity_var,
            command=self._toggle_infinity
        )
        self.infinity_cb.pack(side="left", padx=(12, 0))

        # 5. Action Bar & Progress
        action_row = ttk.Frame(main_container)
        action_row.pack(fill="x", pady=(0, 12))

        self.start_btn = ttk.Button(action_row, text="▶ Mulai Panggilan (Multi-Instance)", style="Accent.TButton",
                                     command=self._start_clicked)
        self.start_btn.pack(side="left")

        self.stop_btn = ttk.Button(action_row, text="⏹ Berhenti", style="Danger.TButton",
                                     command=self._stop_clicked, state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(action_row, mode="indeterminate", style="Horizontal.TProgressbar")
        self.progress.pack(side="left", fill="x", expand=True, padx=(16, 0))

        # 6. Activity Console / Log Panel
        log_panel = ttk.Frame(main_container, style="Panel.TFrame", padding=14)
        log_panel.pack(fill="both", expand=True)

        log_top = ttk.Frame(log_panel, style="Panel.TFrame")
        log_top.pack(fill="x")
        ttk.Label(log_top, text="Log Aktivitas & Monitor Status Rotasi", style="PanelHeading.TLabel").pack(side="left")
        ttk.Button(log_top, text="Bersihkan Log", style="Secondary.TButton", command=self._clear_log).pack(side="right")

        self.log_text = tk.Text(log_panel, height=6, bg=BG_INPUT, fg=FG, font=FONT_MONO,
                                 relief="flat", padx=12, pady=10, state="disabled")
        self.log_text.pack(fill="both", expand=True, pady=(8, 0))

        self.log_text.tag_config("call", foreground="#34d399")
        self.log_text.tag_config("info", foreground=MUTED)
        self.log_text.tag_config("error", foreground="#f87171")
        self.log_text.tag_config("done", foreground="#818cf8")

    # ---------- MicroSIP Manager Actions ----------
    def _refresh_listbox(self):
        def sort_key(path):
            match = re.search(r'[S|s][I|i][P|p](\d+)', path)
            if match:
                return (0, int(match.group(1)))
            return (1, path)

        self.microsip_list.sort(key=sort_key)
        
        # Clear tree items
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, path in enumerate(self.microsip_list, start=1):
            acc_info = read_microsip_account(path)
            username = acc_info['username'] or "-"
            server = acc_info['server'] or "-"
            status = "Siap" if (acc_info['username'] and acc_info['server']) else "Kosong"
            
            self.tree.insert("", "end", iid=str(idx - 1), values=(
                idx,
                path,
                username,
                server,
                status
            ))

        count = len(self.microsip_list)
        self.instance_count_var.set(f"{count} Instansi Terdaftar")
        self.card_inst_var.set(f"{count} Instansi")

    def _auto_detect_on_start(self):
        found = find_all_microsip_candidates()
        if found:
            self.microsip_list = found
        self._refresh_listbox()

    def _auto_detect_all_clicked(self):
        found = find_all_microsip_candidates()
        if found:
            for f in found:
                if f not in self.microsip_list:
                    self.microsip_list.append(f)
            self._refresh_listbox()
            messagebox.showinfo("Auto-Detect Selesai", f"Ditemukan {len(found)} instansi MicroSIP di sistem.")
        else:
            messagebox.showwarning("Tidak Ditemukan", "Tidak ada instansi MicroSIP tambahan terdeteksi secara otomatis.")

    def _get_source_path(self):
        if self.microsip_list:
            return self.microsip_list[0]
        candidates = find_all_microsip_candidates()
        if candidates:
            return candidates[0]
        return None

    def _batch_account_clicked(self):
        """Membuka modal dialog dengan TABEL input Username & Password per baris."""
        source_path = self._get_source_path()
        if not source_path or not os.path.isfile(source_path):
            messagebox.showinfo("Pilih MicroSIP Utama",
                                "Pilih lokasi MicroSIP.exe utama terlebih dahulu untuk dijadikan template master.")
            source_path = filedialog.askopenfilename(
                title="Pilih MicroSIP.exe Utama",
                filetypes=[("MicroSIP executable", "*.exe"), ("Semua File", "*.*")]
            )

        if not source_path or not os.path.isfile(source_path):
            messagebox.showerror("Batal", "File MicroSIP sumber tidak ditemukan.")
            return

        dlg = BatchAccountDialog(self.root, source_path)
        self.root.wait_window(dlg)

        if dlg.created_paths:
            for p in dlg.created_paths:
                if p not in self.microsip_list:
                    self.microsip_list.append(p)
            self._refresh_listbox()
            self._append_log(f"Berhasil membuat {len(dlg.created_paths)} instansi baru!", "info")

    def _setup_account_clicked(self):
        """Membuka dialog pengisian 1 akun SIP pada instansi terpilih."""
        selected = self.tree.selection()
        if not selected:
            if self.microsip_list:
                path = self.microsip_list[0]
            else:
                messagebox.showwarning("Pilih Instansi", "Tambahkan instansi MicroSIP terlebih dahulu.")
                return
        else:
            idx = int(selected[0])
            path = self.microsip_list[idx]

        dlg = SingleAccountDialog(self.root, path)
        self.root.wait_window(dlg)
        self._refresh_listbox()

    def _remove_selected_clicked(self):
        """Menghapus instansi terpilih DAN menghapus foldernya dari disk secara fisik."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Pilih Instansi", "Pilih instansi MicroSIP dari tabel yang ingin dihapus.")
            return

        idx = int(selected[0])
        exe_path = self.microsip_list[idx]
        folder_path = os.path.dirname(exe_path)

        confirm = messagebox.askyesno("Konfirmasi Hapus Permanent",
                                      f"Apakah Anda yakin ingin menghapus instansi ini?\n\nExecutable: {exe_path}\n"
                                      f"Folder {folder_path} dan seluruh isinya akan DIHAPUS DARI DISK.")
        if confirm:
            try:
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path, ignore_errors=True)
                    self._append_log(f"Folder instansi berhasil dihapus: {folder_path}", "info")
            except Exception as e:
                messagebox.showerror("Gagal Hapus Folder", f"Terjadi kesalahan saat menghapus folder {folder_path}: {e}")

            del self.microsip_list[idx]
            self._refresh_listbox()

    # ---------- Execution Controls ----------
    def _start_clicked(self):
        if not self.microsip_list:
            messagebox.showerror("Belum Ada MicroSIP",
                                  "Minimal harus ada 1 instansi MicroSIP.\nKlik '⚡ Tabel Batch Input Akun'.")
            return

        try:
            dial_wait = float(self.dial_wait_var.get())
            hangup_wait = float(self.hangup_wait_var.get())
            if self.infinity_var.get():
                recall_count = 0
            else:
                recall_count = int(self.recall_var.get())
        except ValueError:
            messagebox.showerror("Input Tidak Valid", "Isian detik dan jumlah pengulangan harus berupa angka.")
            return

        self._clear_log()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_event.clear()

        self.status_badge_var.set(" RUNNING ")
        self.status_label.configure(bg=ACCENT)
        self.card_mode_var.set("Berjalan")

        self.progress.start(10)

        raw_text = self.phone_text.get("1.0", "end")
        numbers = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if not numbers:
            messagebox.showerror("Nomor Kosong", "Masukkan minimal 1 nomor tujuan di kolom input nomor.")
            return

        self.worker_thread = threading.Thread(
            target=run_calls,
            args=(list(self.microsip_list), numbers, dial_wait, hangup_wait, recall_count, self.log_queue, self.stop_event),
            daemon=True,
        )
        self.worker_thread.start()

    def _update_phone_count(self, event=None):
        raw_text = self.phone_text.get("1.0", "end")
        numbers = [line.strip() for line in raw_text.splitlines() if line.strip()]
        self.phone_count_var.set(f"{len(numbers)} Nomor Terdeteksi")

    def _toggle_infinity(self):
        if self.infinity_var.get():
            self.recall_spin.configure(state="disabled")
        else:
            self.recall_spin.configure(state="normal")

    def _stop_clicked(self):
        self.stop_event.set()
        self._append_log("Menghentikan proses rotasi panggilan...", "info")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _append_log(self, message, tag="info"):
        self.log_text.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_log_queue(self):
        try:
            while True:
                tag, message = self.log_queue.get_nowait()
                self._append_log(message, tag)
                if tag == "done" or (tag == "info" and "Dihentikan" in message):
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.progress.stop()
                    self.status_badge_var.set(" READY ")
                    self.status_label.configure(bg=SUCCESS)
                    self.card_mode_var.set("Standby")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_log_queue)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    else:
        print("Peringatan: MicroSIP hanya berjalan di Windows.")

    root = tk.Tk()
    login_app = LicenseLoginWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
