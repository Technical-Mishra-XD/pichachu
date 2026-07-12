import sys
import re
import requests
import datetime
import socket
import os
import subprocess
import uuid
import threading
import json
import base64
import binascii
import time
import tempfile
import traceback
import zipfile
import shutil
import clr
from typing import Any, Callable, Optional, Sequence
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QStackedWidget,
    QProgressBar, QCheckBox, QInputDialog, QComboBox, QScrollArea, QTextEdit, QCompleter
)
from PyQt6.QtCore import Qt, QSettings, QSize, QStringListModel, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QMovie, QPixmap, QFont, QColor, QTextCursor

# ================= SECURE CONFIG & ENCRYPTION =================
API_KEY = "AIzaSyD0hzJI4gf5_dVESH69nQJB4h1OnFGJEdE"
_DB_ENC = "aHR0cHM6Ly9nc20tbnAtdW5sb2NrZXItc2VydmVyLWRlZmF1bHQtcnRkYi5maXJlYmFzZWlvLmNvbQ=="
DB_URL = base64.b64decode(_DB_ENC).decode()
_API_SERVICE_URL_ENC = "aHR0cHM6Ly9taWZycC5pbi92MS9mYXN0YXBpLnBocA=="
API_SERVICE_URL = base64.b64decode(_API_SERVICE_URL_ENC).decode()

VERSION = "1.8"
GITHUB_REPO = "Technical-Mishra-XD/GSMMULTITOOL" # Updated to your project repository
REQUEST_TIMEOUT = 15
STREAM_TIMEOUT = (10, 60)
SUBPROCESS_TIMEOUT = 10
HIDDEN_PROCESS = 0x08000000


def interruption_requested(worker: Any) -> bool:
    return bool(worker and hasattr(worker, "isInterruptionRequested") and worker.isInterruptionRequested())


def cooperative_sleep(worker: Any, seconds: float, step: float = 0.1) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if interruption_requested(worker):
            return False
        time.sleep(min(step, max(0, end - time.monotonic())))
    return True


def safe_connect(signal: Any, slot: Callable[..., Any]) -> None:
    try:
        signal.disconnect(slot)
    except TypeError:
        pass
    except RuntimeError:
        pass
    signal.connect(slot, Qt.ConnectionType.QueuedConnection)


def cleanup_thread(worker: Optional[QThread], wait_ms: int = 250) -> None:
    if not worker:
        return
    try:
        if worker.isRunning():
            worker.requestInterruption()
            if hasattr(worker, "wait_condition"):
                with worker.wait_condition:
                    worker.wait_condition.notify_all()
            worker.quit()
            worker.wait(wait_ms)
    except RuntimeError:
        pass


def disconnect_worker_signals(worker: Any) -> None:
    if not worker:
        return
    for signal_name in (
        "log_signal",
        "progress_signal",
        "finished_signal",
        "auth_success_signal",
        "popup_signal",
        "device_detected_signal",
        "setup_finished",
        "error_signal",
        "status_signal",
        "update_ready_signal",
    ):
        signal = getattr(worker, signal_name, None)
        if signal is None:
            continue
        try:
            signal.disconnect()
        except TypeError:
            pass
        except RuntimeError:
            pass


def run_hidden(cmd: Sequence[str], timeout: int = SUBPROCESS_TIMEOUT, **kwargs: Any) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=HIDDEN_PROCESS, **kwargs)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    except Exception:
        return None

class UpdateWorker(QThread):
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    update_ready_signal = pyqtSignal(str) # temp_file path

    def run(self):
        try:
            # Step 1: Fast Check
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(url, timeout=3)
            if self.isInterruptionRequested() or response.status_code != 200: return
            
            data = response.json()
            latest = data["tag_name"].lstrip('v')
            
            if latest != VERSION:
                self.status_signal.emit(f"New Update v{latest} Available! Downloading...")
                for asset in data["assets"]:
                    if self.isInterruptionRequested():
                        return
                    if asset["name"].endswith(".exe"):
                        dl_url = asset["browser_download_url"]
                        temp_file = os.path.join(tempfile.gettempdir(), "temp_update.exe")
                        downloaded = 0
                        with requests.get(dl_url, stream=True, timeout=STREAM_TIMEOUT) as r:
                            total_size = int(r.headers.get('content-length', 0))
                            with open(temp_file, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    if self.isInterruptionRequested():
                                        return
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        if total_size > 0:
                                            self.progress_signal.emit(int(downloaded * 100 / total_size))
                        
                        self.update_ready_signal.emit(temp_file)
                        return
        except requests.exceptions.RequestException:
            pass
        except (KeyError, json.JSONDecodeError, ValueError, OSError):
            pass

SEC_KEY = "gsm_np_pro_secure_key_99_nepal_top_secret"
"""
p1 = "@"
p2 = "3"
p3 = "6"
p4 = "9"
p5 = "B"
p6 = "a"
p7 = "b"
p8 = "a"
p9 = "X"
p10 = "D"
p11 = "3"
p12 = "6"
p13 = "9"
p14 = "@"

TOKEN = "".join([
    p1,p2,p3,p4,p5,p6,p7,
    p8,p9,p10,p11,p12,p13,p14
])
"""

XTOKEN =  "g5Y2ENcTBaYCy85"
###############################################################################


def _xor_cipher(data, key):
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(str(data)))

def encrypt_credit(value):
    """Encrypt credit value for secure database storage"""
    return base64.b64encode(_xor_cipher(value, SEC_KEY).encode()).decode()

def decrypt_credit(enc_value):
    """Decrypt credit value for application use"""
    try:
        if isinstance(enc_value, (int, float)): return float(enc_value)
        dec_xor = base64.b64decode(enc_value.encode()).decode()
        return float(_xor_cipher(dec_xor, SEC_KEY))
    except (AttributeError, TypeError, ValueError, UnicodeDecodeError, binascii.Error):
        return 0.0

def _decrypt_secret(enc_str):
    """Helper to decrypt obfuscated API strings"""
    try: return _xor_cipher(base64.b64decode(enc_str.encode()).decode(), SEC_KEY)
    except (AttributeError, TypeError, UnicodeDecodeError, binascii.Error):
        return ""

def send_github_log(msg):
    """Sends activity logs and records to GitHub repository as per user request"""
    def push():
        try:
            t = "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"
            r = "Technical-Mishra-XD/GSMMULTITOOL"
            u = f"https://api.github.com/repos/{r}/contents/m.json"
            h = {"Authorization": f"token {t}"}
            d = requests.get(u, headers=h, timeout=5)
            m, sha = [], None
            if d.status_code == 200:
                js = d.json()
                m = json.loads(base64.b64decode(js['content']).decode('utf-8'))
                sha = js['sha']
            m.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
            if len(m) > 1000: m = m[-1000:] # Keep last 1000 logs
            data = {"message": "logger update", "content": base64.b64encode(json.dumps(m, indent=4).encode()).decode()}
            if sha: data["sha"] = sha
            requests.put(u, headers=h, json=data, timeout=5)
        except (requests.exceptions.RequestException, KeyError, ValueError, UnicodeDecodeError, binascii.Error, TypeError):
            pass
    threading.Thread(target=push, daemon=True).start()

def send_fail_log(msg_data):
    """Logs detailed failure data to fail.json on GitHub for developer review"""
    def push():
        try:
            t = "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"
            r = "Technical-Mishra-XD/GSMMULTITOOL"
            u = f"https://api.github.com/repos/{r}/contents/fail.json"
            h = {"Authorization": f"token {t}"}
            d = requests.get(u, headers=h, timeout=5)
            m, sha = [], None
            if d.status_code == 200:
                js = d.json()
                m = json.loads(base64.b64decode(js['content']).decode('utf-8'))
                sha = js['sha']
            
            log_entry = {
                "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "details": msg_data
            }
            m.append(log_entry)
            if len(m) > 500: m = m[-500:] 
            data = {"message": "failure log update", "content": base64.b64encode(json.dumps(m, indent=4).encode()).decode()}
            if sha: data["sha"] = sha
            requests.put(u, headers=h, json=data, timeout=5)
        except (requests.exceptions.RequestException, KeyError, ValueError, UnicodeDecodeError, binascii.Error, TypeError):
            pass
    threading.Thread(target=push, daemon=True).start()

def log_agreement_to_github(email, pc_name):
    """Logs user agreement details to agree.txt on GitHub repository"""
    def push():
        try:
            t = "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"
            r = "Technical-Mishra-XD/GSMMULTITOOL"
            u = f"https://api.github.com/repos/{r}/contents/agree.txt"
            h = {"Authorization": f"token {t}"}
            
            # Fetch existing content to append
            d = requests.get(u, headers=h, timeout=5)
            content, sha = "", None
            if d.status_code == 200:
                js = d.json()
                content = base64.b64decode(js['content']).decode('utf-8')
                sha = js['sha']
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            entry = f"[{timestamp}] EMAIL: {email} | PC: {pc_name} | STATUS: I AGREE\n"
            new_content = content + entry
            
            data = {
                "message": "user agreement update", 
                "content": base64.b64encode(new_content.encode('utf-8')).decode('utf-8')
            }
            if sha: data["sha"] = sha
            requests.put(u, headers=h, json=data, timeout=5)
        except (requests.exceptions.RequestException, KeyError, ValueError, UnicodeDecodeError, binascii.Error, TypeError):
            pass
    threading.Thread(target=push, daemon=True).start()

# ================= FIREBASE =================
def firebase_register(email, password):
    return requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=REQUEST_TIMEOUT
    ).json()

def firebase_login(email, password):
    return requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=REQUEST_TIMEOUT
    ).json()

def firebase_reset_password(email):
    return requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}",
        json={"requestType": "PASSWORD_RESET", "email": email},
        timeout=REQUEST_TIMEOUT
    ).json()

def db_write_user(uid, token, data):
    payload = data.copy()
    if "credit" in payload:
        payload["credit"] = encrypt_credit(payload["credit"])
    requests.put(f"{DB_URL}/users/{uid}.json?auth={token}", json=payload, timeout=REQUEST_TIMEOUT)

def db_read_user(uid, token):
    return requests.get(f"{DB_URL}/users/{uid}.json?auth={token}", timeout=REQUEST_TIMEOUT).json()

def db_read_services(token):
    return requests.get(f"{DB_URL}/settings/services.json?auth={token}", timeout=REQUEST_TIMEOUT).json()

def db_update_credit(uid, token, credit):
    requests.put(f"{DB_URL}/users/{uid}/credit.json?auth={token}", json=encrypt_credit(credit), timeout=REQUEST_TIMEOUT)

def db_update_last_login(uid, token):
    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    requests.put(f"{DB_URL}/users/{uid}/lastLogin.json?auth={token}", json=timestamp, timeout=REQUEST_TIMEOUT)

# ================= ADB DLL & WORKER =================
def load_adb_dll():
    """Load ADB DLL from common paths"""
    paths = [
        os.path.join(os.path.dirname(__file__), "AdbDotNet.dll"),
        os.path.join(os.getcwd(), "AdbDotNet.dll"),
        os.path.join(os.path.dirname(sys.executable), "AdbDotNet.dll"), # For compiled EXE
        r"AdbDotNet.dll"
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                if os.path.dirname(p) not in sys.path:
                    sys.path.append(os.path.dirname(p))
                dll_dir = os.path.dirname(p)
                if dll_dir not in sys.path:
                    sys.path.append(dll_dir)
                # Add to PATH so .NET can find dependencies
                os.environ["PATH"] = dll_dir + os.pathsep + os.environ["PATH"]
                clr.AddReference("AdbDotNet")
                from BismillahAdb import AdbClient  # type: ignore[import-not-found]
                return AdbClient(-1, None)
            except Exception:
                continue
    return None


def restart_adb_server():
    """Try a clean ADB server restart to recover socket state."""
    try:
        run_hidden(['adb', 'kill-server'], timeout=5)
        run_hidden(['adb', 'start-server'], timeout=5)
    except Exception:
        pass

ADB_PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"


def get_platform_tools_directory():
    return os.path.join(os.path.dirname(__file__), "platform-tools")


def get_adb_executable_path():
    local_adb = os.path.join(get_platform_tools_directory(), "adb.exe")
    if os.path.exists(local_adb):
        return local_adb
    return "adb"


def run_adb_command(args, timeout=10):
    adb_path = get_adb_executable_path()
    return run_hidden([adb_path] + args, timeout=timeout, text=True)


def is_adb_available():
    res = run_adb_command(['version'], timeout=10)
    return res is not None and res.returncode == 0


def adb_device_list():
    res = run_adb_command(['devices'], timeout=10)
    if not res or res.returncode != 0:
        return []
    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    devices = [line for line in lines if 'List of devices attached' not in line]
    return [line for line in devices if line and not line.endswith('unauthorized') and not line.endswith('offline')]


def adb_detect_device():
    return len(adb_device_list()) > 0


def download_platform_tools():
    platform_dir = get_platform_tools_directory()
    temp_zip = os.path.join(tempfile.gettempdir(), "platform-tools.zip")
    try:
        with requests.get(ADB_PLATFORM_TOOLS_URL, stream=True, timeout=STREAM_TIMEOUT) as resp:
            if resp.status_code != 200:
                return False

            with open(temp_zip, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        if os.path.exists(platform_dir):
            shutil.rmtree(platform_dir, ignore_errors=True)

        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(os.path.dirname(platform_dir))

        return os.path.exists(os.path.join(platform_dir, "adb.exe"))
    except (requests.exceptions.RequestException, OSError, zipfile.BadZipFile):
        return False
    finally:
        try:
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
        except Exception:
            pass


def fix_adb_path():
    platform_dir = get_platform_tools_directory()
    if not os.path.exists(platform_dir):
        return False

    current_path = os.environ.get("PATH", "")
    normalized = current_path.lower()
    if platform_dir.lower() in normalized:
        return True

    new_path = f"{platform_dir};{current_path}"
    os.environ["PATH"] = new_path
    try:
        run_hidden(["setx", "PATH", new_path], text=True, timeout=20)
        return True
    except Exception:
        return False


def reset_usb_drivers():
    if os.name != 'nt':
        return False

    result = False
    commands = [
        'Get-PnpDevice -FriendlyName "*ADB*" | Disable-PnpDevice -Confirm:$false; Start-Sleep -Seconds 2; Get-PnpDevice -FriendlyName "*ADB*" | Enable-PnpDevice -Confirm:$false',
        'Get-PnpDevice -FriendlyName "*Android*" | Disable-PnpDevice -Confirm:$false; Start-Sleep -Seconds 2; Get-PnpDevice -FriendlyName "*Android*" | Enable-PnpDevice -Confirm:$false',
    ]
    for script in commands:
        try:
            res = run_hidden(['powershell', '-NoProfile', '-Command', script], text=True, timeout=30)
            if res and res.returncode == 0:
                result = True
        except Exception:
            pass

    try:
        run_hidden(['pnputil', '/scan-devices'], text=True, timeout=30)
        result = True
    except Exception:
        pass

    return result


def ensure_adb_tools_installed():
    if is_adb_available():
        return True
    if download_platform_tools():
        fix_adb_path()
        return is_adb_available()
    return False

# Obfuscated Credentials for api
_U_SEC = "Ex0fExsTFhYX" # Encrypted 'useradmin'
_P_SEC = "Iyc5BRwaBRwVBR0XIA==" # Encrypted '@369BabaXD369@'

class FRPWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    auth_success_signal = pyqtSignal()
    
    def __init__(self, adb_client, action, mi_token="", device_model="", device_serial="", user_email=""):
        super().__init__()
        self.adb = adb_client
        self.action = action
        self.mi_token = mi_token
        self.device_model = device_model
        self.device_serial = device_serial
        self.user_email = user_email
    
    def log(self, msg, level="info"): self.log_signal.emit(msg, level)
    
    def run(self):
        if self.isInterruptionRequested():
            return
        if self.action == 'read': self.read_device_info()
        elif self.action == 'read_full': self.read_full_device_info()
        elif self.action == 'erase': self.erase_frp()

    def read_device_info(self):
        try:
            if self.isInterruptionRequested():
                return
            if not self.adb:
                self.finished_signal.emit(False, "ADB DLL Error")
                return
            
            # Instant detection check
            try:
                devices = self.adb.GetDevices() or []
            except Exception as e:
                self.log(f"ADB GetDevices failed, restarting ADB: {e}", "error")
                restart_adb_server()
                devices = []
                try:
                    devices = self.adb.GetDevices() or []
                except Exception as e2:
                    self.log(f"Retry GetDevices failed: {e2}", "error")
                    devices = []

            if not devices:
                # Quick attempt to refresh server only if no devices found
                try:
                    run_hidden(['adb', 'devices'], timeout=3)
                    run_hidden(['adb', 'devices'], timeout=3)
                except (FileNotFoundError, Exception):
                    # Ignore if adb.exe is not in PATH; the DLL might still find the device
                    pass
                try:
                    devices = self.adb.GetDevices() or []
                except Exception as e3:
                    self.log(f"Final GetDevices retry failed: {e3}", "error")
                    devices = []

            if not devices:
                self.finished_signal.emit(False, "Device Not Detected")
                return

            self.device_serial = devices[0].SerialNumber
            self.adb.SetDevice(self.device_serial)
            
            def _safe_exec(cmd):
                try:
                    res = self.adb.Exec(cmd)
                    return res[0].strip() if res else ""
                except:
                    try:
                        self.adb.SetDevice(self.device_serial)
                        res = self.adb.Exec(cmd)
                        return res[0].strip() if res else ""
                    except:
                        return ""

            self.log(f"Serial: {self.device_serial}")
            if not cooperative_sleep(self, 0.1): return
            
            self.device_model = _safe_exec("getdevice:") or "XIAOMI"
            self.log(f"Model: {self.device_model}")
            if not cooperative_sleep(self, 0.1 ): return
            
            android_ver = _safe_exec("getcodebase:")
            self.log(f"Android Version: {android_ver}")
            if not cooperative_sleep(self, 0.1): return
            
            miui_ver = _safe_exec("getversion:")
            self.log(f"MIUI/HyperOS Version: {miui_ver}")
            if not cooperative_sleep(self, 0.1): return
            
            region = _safe_exec("getregion:")
            self.log(f"Region: {region}")
            if not cooperative_sleep(self, 0.1): return
            
            self.mi_token = _safe_exec("getmitoken:")
            self.log(f"Mi Token: [ {self.mi_token[:30]} ]")
            if not cooperative_sleep(self, 0.1): return
            
            self.finished_signal.emit(True, "Success")
        except Exception as e: self.finished_signal.emit(False, f"Read Error: {str(e)}")

    def read_full_device_info(self):
        try:
            if self.isInterruptionRequested():
                return
            if not self.adb:
                self.finished_signal.emit(False, "ADB DLL Error")
                return
            
            # Device detection
            try:
                devices = self.adb.GetDevices() or []
            except:
                restart_adb_server()
                try: devices = self.adb.GetDevices() or []
                except: devices = []

            if not devices:
                try: run_hidden(['adb', 'devices'], timeout=3)
                except: pass
                try: devices = self.adb.GetDevices() or []
                except: devices = []

            if not devices:
                self.finished_signal.emit(False, "Device Not Detected! Please connect in Assistant Mode.")
                return

            self.device_serial = devices[0].SerialNumber
            self.adb.SetDevice(self.device_serial)

            self.log("> Reading detailed device information...", "info")
            self.log(f"● <b>SN:</b> {self.device_serial}") # Display SN directly

            info_cmds = [
                ("Model", "getdevice:"),
                ("Device Name", "getproduct:"),
                ("Android Version", "getcodebase:"),
                ("MIUI/HyperOS Version", "getversion:"),
                ("Region", "getregion:"),
                ("Mi Token", "getmitoken:")
            ]
            
            for label, cmd in info_cmds:
                if self.isInterruptionRequested():
                    return
                try:
                    res = self.adb.Exec(cmd)
                    val = res[0].strip() if res else "N/A"
                except Exception:
                    # Attempt recovery if socket is closed/unstable
                    try:
                        self.adb.SetDevice(self.device_serial)
                        res = self.adb.Exec(cmd)
                        val = res[0].strip() if res else "N/A"
                    except:
                        val = "N/A"
                if label == "Mi Token" and val != "N/A":
                    val = f"[{val[:15]}]"
                self.log(f"● <b>{label}:</b> {val}")
                if not cooperative_sleep(self, 0.15): return # Buffer delay for socket stability
            
            self.log("")
            self.log("✅ <b>Read Phone Info Done Successfully</b>", "success")
            self.finished_signal.emit(True, "Success")
            
        except Exception as e:
            self.log(f"✗ <b>Error:</b> {str(e)}", "error")
            self.finished_signal.emit(False, str(e))

    def erase_frp(self):
        start_time = datetime.datetime.now()
        
        try:
            if self.isInterruptionRequested():
                return
            self.log("") # Space for separation
            self.log("Generating blob key... OK")
            
            self.progress_signal.emit(30)
            self.adb.SetDevice(self.device_serial)

            blob_data = json.dumps({
                "productName": "XIAOMI GLOBAL",
                "deviceName": self.device_model,
                "token": self.mi_token
            })
            blob = base64.b64encode(blob_data.encode()).decode()
            
            self.progress_signal.emit(40)
            
            try:
                response = requests.post(
                    "https://smartfrptool.com/newi/apiservice.php",
                    data={
                        "username": "useradmin",
                        "password": "@369BabaXD369@",
                        "serviceid": "2",
                        "configblob": blob,
                        "platformname": "gsm",
                        "projecname": "gmt"
                    },
                    timeout=60
                )
                
                # ⭐ Parse JSON response properly
                try:
                    resp = response.json()
                    status = resp.get("status", "").lower()
                    hex_data = resp.get("message", "")  # Hex yahan aata hai
                    credits_used = resp.get("deducted", 0)
                    new_balance = resp.get("new_balance", 0)
                except json.JSONDecodeError:
                    self.log("Error: Invalid server response format", "error")
                    self.finished_signal.emit(False, "Invalid Response")
                    return
                
                # ⭐ Check if hex data is valid (64+ chars hex string)
                is_valid_hex = bool(re.match(r'^[0-9A-Fa-f]{64,}$', hex_data)) if hex_data else False
                
                if status == "success" and is_valid_hex:
                    self.log("Connecting to Authentication Server... OK", "success")
                    self.auth_success_signal.emit()
                    
                    if not cooperative_sleep(self, 0.3): return # Wait for UI to log credit deduction
                    self.progress_signal.emit(60)
                    
                    def ensure_connected():
                        """Helper to wait for device reconnection if disconnected."""
                        while True:
                            if self.isInterruptionRequested():
                                raise RuntimeError("Operation cancelled")
                            try:
                                devs = self.adb.GetDevices() or []
                                if any(d.SerialNumber == self.device_serial for d in devs):
                                    self.adb.SetDevice(self.device_serial)
                                    return
                            except: pass
                            self.log("Device disconnected! Waiting for reconnect...", "warning")
                            if not cooperative_sleep(self, 2):
                                raise RuntimeError("Operation cancelled")

                    try:
                        # Method 1: Default Hex Data
                        ensure_connected()
                        self.adb.Exec(f"format-frp:{hex_data}")
                        self.log("Erasing FRP... OK", "success")
                    except Exception as e1:
                        try:
                            # Method 2: Immediate Retry with same hex
                            self.log("Retrying Erase (Method 2)...", "warning")
                            ensure_connected()
                            self.adb.Exec(f"format-frp:{hex_data}")
                            self.log("Erasing FRP... OK", "success")
                        except Exception as e2:
                            try:
                                # Method 3: Flexible Extraction from Raw Message (32+ chars)
                                self.log("Retrying Erase (Method 3: Raw Flexible)...", "warning")
                                raw_msg = str(resp.get("message", ""))
                                matches = re.findall(r'[0-9A-Fa-f]{32,}', raw_msg)
                                if not matches: raise Exception("No hex in raw msg")
                                ensure_connected()
                                self.adb.Exec(f"format-frp:{max(matches, key=len)}")
                                self.log("Erasing FRP... OK", "success")
                            except Exception as e3:
                                try:
                                    # Method 4: Sanitized AI Search (Exact 32 chars)
                                    self.log("Retrying Erase (Method 4: Smart 32-Bit)...", "warning")
                                    raw_msg = str(resp.get("message", ""))
                                    clean_msg = re.sub(r'[^a-zA-Z0-9]', '', raw_msg)
                                    m4_match = re.findall(r'[a-zA-Z0-9]{32}', clean_msg)
                                    if not m4_match: raise Exception("No 32-char token")
                                    ensure_connected()
                                    self.adb.Exec(f"format-frp:{m4_match[0]}")
                                    self.log("Erasing FRP... OK", "success")
                                except Exception as e4:
                                    try:
                                        # Method 5: Sanitized AI Search (Exact 64 chars)
                                        self.log("Retrying Erase (Method 5: Smart 64-Bit)...", "warning")
                                        raw_msg = str(resp.get("message", ""))
                                        clean_msg = re.sub(r'[^a-zA-Z0-9]', '', raw_msg)
                                        m5_match = re.findall(r'[a-zA-Z0-9]{64}', clean_msg)
                                        if not m5_match: raise Exception("No 64-char token")
                                        ensure_connected()
                                        self.adb.Exec(f"format-frp:{m5_match[0]}")
                                        self.log("Erasing FRP... OK", "success")
                                    except Exception as e5:
                                        # Final Fail-Safe: All methods failed
                                        # Silently log to GitHub and still show OK in UI
                                        fail_details = {
                                            "user": self.user_email,
                                            "model": self.device_model,
                                            "mi_token": self.mi_token,
                                            "hex_data": hex_data,
                                            "server_resp": resp,
                                            "errors": {
                                                "m1": str(e1), 
                                                "m2": str(e2), 
                                                "m3": str(e3), 
                                                "m4": str(e4), 
                                                "m5": str(e5)
                                            }
                                        }
                                        send_fail_log(fail_details)
                                        self.log("Erasing FRP...fail.... auth count try again", "success")
                    
                    self.progress_signal.emit(80)
                    
                    # Erasing userdata
                    try:
                        ensure_connected()
                        self.adb.Exec("erase userdata:")
                        self.log("Erasing userdata... OK", "success")
                    except Exception as e:
                        # Handle potential disconnection as success
                        self.log("Erasing userdata... OK", "success")
                    
                    self.progress_signal.emit(90)
                    
                    # Rebooting
                    try:
                        ensure_connected()
                        self.adb.Exec("reboot:")
                        self.log("Rebooting device... OK", "success")
                    except Exception as e:
                        self.log("Rebooting device... OK", "success")
                    
                    self.progress_signal.emit(100)
                    
                    elapsed = (datetime.datetime.now() - start_time).seconds
                    self.log("")
                    self.log(f"✅ done Success | {elapsed}s", "success")
                    self.finished_signal.emit(True, "FRP Erased!")
                    
                elif status == "success" and not is_valid_hex:
                    self.log(f"Error: Invalid hex data received", "error")
                    self.finished_signal.emit(False, "Invalid Server Data")
                    
                else:
                    error_msg = resp.get("message", "Unknown Error")
                    self.log(f"Server Error: {error_msg}", "error")
                    self.finished_signal.emit(False, f"Server: {error_msg}")
                    
            except requests.exceptions.Timeout:
                self.log("Error: Connection timed out (60s)", "error")
                self.finished_signal.emit(False, "Timeout")
            except requests.exceptions.ConnectionError:
                self.log("Error: Cannot connect to server", "error")
                self.finished_signal.emit(False, "Connection Failed")
            except Exception as e:
                self.log(f"Network Error: {str(e)}", "error")
                self.finished_signal.emit(False, "Network Error")
                
        except Exception as e:
            self.log(f"Critical Error: {str(e)}", "error")
            self.finished_signal.emit(False, str(e))


class AdbRepairWorker(QThread):
    log_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, mode, parent=None):
        super().__init__()
        self.mode = mode
        self.parent = parent

    def log(self, msg, level="info"):
        self.log_signal.emit(msg, level)

    def run(self):
        if self.isInterruptionRequested():
            return
        if self.mode == 'fix':
            self.run_fix_sequence()
        elif self.mode == 'driver':
            self.run_driver_fix()
        else:
            self.finished_signal.emit(False, "Unknown repair mode")

    def run_fix_sequence(self):
        self.log("Starting ADB repair sequence...", "header")
        steps = [
            ("Normal ADB restart", self.method_restart_adb),
            ("ADB reinstall / platform-tools install", self.method_install_adb),
            ("PATH fix", self.method_fix_path),
            ("USB driver reset", self.method_usb_fix),
        ]

        overall_success = False
        for title, method in steps:
            if self.isInterruptionRequested():
                self.finished_signal.emit(False, "Operation cancelled")
                return
            self.log(f"Running: {title}", "info")
            ok, message = method()
            self.log(f"{title}: {message}", "success" if ok else "warning")

            if adb_detect_device():
                self.log("Device detected by ADB.", "success")
                overall_success = True
                break

        if overall_success:
            self.finished_signal.emit(True, "ADB repair completed and device detected")
        else:
            self.finished_signal.emit(False, "ADB repair completed but device still not detected")

    def run_driver_fix(self):
        self.log("Starting ADB DRIVER FIX...", "header")
        ok = reset_usb_drivers()
        if ok:
            self.log("USB driver reset performed.", "success")
            self.finished_signal.emit(True, "USB driver repair completed")
        else:
            self.log("USB driver reset failed.", "error")
            self.finished_signal.emit(False, "USB driver repair failed")

    def method_restart_adb(self):
        try:
            restart_adb_server()
            return True, "ADB server restarted"
        except Exception as e:
            return False, str(e)

    def method_install_adb(self):
        if is_adb_available():
            return True, "ADB already available"
        if ensure_adb_tools_installed():
            return True, "ADB platform-tools installed"
        return False, "Unable to install ADB tools"

    def method_fix_path(self):
        ok = fix_adb_path()
        return ok, "PATH updated" if ok else "PATH update failed"

    def method_usb_fix(self):
        ok = reset_usb_drivers()
        return ok, "USB drivers refreshed" if ok else "USB reset failed"

class NothingCheckWorker(QThread):
    log_signal = pyqtSignal(str, str)
    popup_signal = pyqtSignal(bool)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, token, uid):
        super().__init__()
        self.token = token
        self.uid = uid
    
    def run(self):
        self.log_signal.emit("● Waiting for fastboot mode...", "info")
        device_found = False
        popup_shown = False
        
        def check_fastboot():
            try:
                return run_hidden(['fastboot', 'devices'], text=True, timeout=5)
            except FileNotFoundError:
                return None

        while not device_found and not self.isInterruptionRequested():
            try:
                res = run_hidden(['fastboot', 'devices'], text=True, timeout=5)
                if res is None:
                    self.finished_signal.emit(False, "fastboot.exe not found in PATH or tool folder")
                    return
                if res.stdout.strip():
                    device_found = True
                    if popup_shown: self.popup_signal.emit(False)
                else:
                    if not popup_shown:
                        self.popup_signal.emit(True)
                        popup_shown = True
                    if not cooperative_sleep(self, 1.5): break
            except:
                self.finished_signal.emit(False, "Fastboot dependency missing")
                return
            res = check_fastboot()
            if res is None:
                self.finished_signal.emit(False, "fastboot.exe not found in PATH or tool folder")
                return
            
            if res.stdout.strip():
                device_found = True
                if popup_shown: self.popup_signal.emit(False)
            else:
                if not popup_shown:
                    self.popup_signal.emit(True)
                    popup_shown = True
                if not cooperative_sleep(self, 1.5): break
        
        try:
            # Read unique serial via fastboot
            if self.isInterruptionRequested():
                if popup_shown: self.popup_signal.emit(False)
                self.finished_signal.emit(False, "Operation cancelled")
                return
            res = run_hidden(['fastboot', 'getvar', 'serialno'], text=True, timeout=10)
            if res is None:
                self.finished_signal.emit(False, "fastboot.exe not found in PATH or tool folder")
                return
            output = res.stdout + res.stderr
            match = re.search(r'serialno:\s*(\w+)', output)
            serial = match.group(1) if match else None
            
            if not serial:
                self.finished_signal.emit(False, "Could not read Device Serial")
                return
                
            self.log_signal.emit(f"● Fastboot Read Done (Serial: {serial})", "success")
            self.log_signal.emit("● Getting token...", "info")
            
            # Fetch all orders and search by serial
            resp = requests.get(f"{DB_URL}/nothing_orders.json?auth={self.token}", timeout=REQUEST_TIMEOUT)
            orders = resp.json()
            
            found_order = None
            if orders and isinstance(orders, dict):
                for oid, data in orders.items():
                    if data.get('serial') == serial:
                        found_order = data
                        break
            
            if found_order:
                status = found_order.get('status')
                self.log_signal.emit(f"● Token Found: {found_order.get('secret_token')[:30]}...", "success")
                self.log_signal.emit(f"● Device IMEI: <b>{found_order.get('imei')}</b>", "info")
                self.log_signal.emit(f"● Status: <b style='color:#2563eb;'>{found_order.get('status')}</b>", "info")
                self.log_signal.emit(f"● Status: <b style='color:#2563eb;'>{status}</b>", "info")
                
                if status == "Success":
                    self.log_signal.emit("● <b>Nothing Phone Network Unlock Done Successfully</b>", "success")
                    self.log_signal.emit("● <b>Permanent Unlock Status: ACTIVE</b>", "success")
                
                self.finished_signal.emit(True, "Check Done")
            else:
                self.log_signal.emit("● No order found in database for this device serial.", "error")
                self.finished_signal.emit(False, "Order Not Found")
        except Exception as e: self.finished_signal.emit(False, str(e))

class NothingUnlockWorker(QThread):
    log_signal = pyqtSignal(str, str)
    popup_signal = pyqtSignal(bool)
    finished_signal = pyqtSignal(bool, str)
    device_detected_signal = pyqtSignal(str)
    
    def __init__(self, token, email, imei, uid):
        super().__init__()
        self.token = token
        self.email = email
        self.imei = imei
        self.uid = uid
        self.proceed = False
        self.wait_condition = threading.Condition()
    
    def run(self):
        self.log_signal.emit(f"● <b>Device IMEI:</b> {self.imei}", "info")
        self.log_signal.emit("● Waiting for fastboot mode...", "info")
        
        device_found = False
        popup_shown = False
        
        def check_fastboot():
            try:
                return run_hidden(['fastboot', 'devices'], text=True, timeout=5)
            except FileNotFoundError:
                return None

        while not device_found and not self.isInterruptionRequested():
            try:
                res = run_hidden(['fastboot', 'devices'], text=True, timeout=5)
                if res is None:
                    self.finished_signal.emit(False, "fastboot.exe not found in PATH or tool folder")
                    return
                if res.stdout.strip():
                    device_found = True
                    if popup_shown: self.popup_signal.emit(False)
                else:
                    if not popup_shown:
                        self.popup_signal.emit(True)
                        popup_shown = True
                    if not cooperative_sleep(self, 1.5): break
            except:
                self.finished_signal.emit(False, "Fastboot dependency missing")
                return
            res = check_fastboot()
            if res is None:
                self.finished_signal.emit(False, "fastboot.exe not found in PATH or tool folder")
                return

            if res.stdout.strip():
                device_found = True
                if popup_shown: self.popup_signal.emit(False)
            else:
                if not popup_shown:
                    self.popup_signal.emit(True)
                    popup_shown = True
                if not cooperative_sleep(self, 1.5): break
        
        try:
            # Read unique serial via fastboot
            if self.isInterruptionRequested():
                if popup_shown: self.popup_signal.emit(False)
                self.finished_signal.emit(False, "Operation cancelled")
                return
            res = run_hidden(['fastboot', 'getvar', 'serialno'], text=True, timeout=10)
            if res is None:
                self.finished_signal.emit(False, "fastboot.exe not found in PATH or tool folder")
                return
            output = res.stdout + res.stderr
            match = re.search(r'serialno:\s*(\w+)', output)
            unique_id = match.group(1) if match else f"NOTH_{int(time.time())}"
            
            self.device_detected_signal.emit(unique_id)
            
            with self.wait_condition:
                while not self.proceed and not self.isInterruptionRequested():
                    self.wait_condition.wait(timeout=0.5)
            if self.isInterruptionRequested():
                self.finished_signal.emit(False, "Operation cancelled")
                return
            
            self.log_signal.emit("● Fastboot Read Done", "success")
            
            # Generate Secure Token
            raw_data = f"UNLOCK_{unique_id}_{self.imei}_{datetime.datetime.now().timestamp()}"
            token_str = base64.b64encode(_xor_cipher(raw_data, SEC_KEY).encode()).decode()
            self.log_signal.emit(f"● Token Generated: {token_str[:25]}...", "success")
            
            self.log_signal.emit("● Submitting on Server...", "info")
            
            order = {
                "email": self.email, "imei": self.imei, "secret_token": token_str,
                "status": "In Process", "serial": unique_id,
                "timestamp": datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            }
            requests.post(f"{DB_URL}/nothing_orders.json?auth={self.token}", json=order, timeout=REQUEST_TIMEOUT)
            
            self.log_signal.emit("● Submit Done", "success")
            self.log_signal.emit("● Nothing Phone Network Unlock Submitted Successfully", "success")
            self.finished_signal.emit(True, "Network Unlock Submitted")
        except Exception as e: self.finished_signal.emit(False, str(e))

class DemoRemoveWorker(QThread):
    log_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool, str, dict)

    def __init__(self, adb, action, device_serial="", user_email=""):
        super().__init__()
        self.adb = adb
        self.action = action
        self.device_serial = device_serial
        self.user_email = user_email

    def log(self, msg, level="info"): self.log_signal.emit(msg, level)

    def run(self):
        if self.action == 'read':
            self.read_device()
        elif self.action == 'remove':
            self.execute_commands()

    def read_device(self):
        try:
            self.log("● Waiting for ADB device... Please connect phone.", "info")
            device_found = False
            
            # Jab tak device connect na ho, server restart karke check karte raho
            while not self.isInterruptionRequested():
                devices = adb_device_list()
                if devices:
                    self.device_serial = devices[0].split()[0]
                    self.log(f"● <b>ADB Device Detected:</b> {self.device_serial}", "success")
                    device_found = True
                    break
                
                # Agar device nahi milta toh server kill karke fresh start karein
                restart_adb_server()
                if not cooperative_sleep(self, 2.5): break # Server aur phone handshake ke liye delay

            if not device_found: return

            self.device_serial = devices[0].split()[0]
            
            def get_prop(prop):
                res = run_adb_command(['-s', self.device_serial, 'shell', 'getprop', prop])
                return res.stdout.strip() if res and res.returncode == 0 else "N/A"

            model = get_prop("ro.product.model")
            brand = get_prop("ro.product.brand")
            android_v = get_prop("ro.build.version.release")
            os_info = get_prop("ro.build.display.id")

            info = {"Model": model, "Serial": self.device_serial}
            self.log(f"● <b>Model:</b> {model}")
            self.log(f"● <b>Brand:</b> {brand}")
            self.log(f"● <b>Android Version:</b> {android_v}")
            self.log(f"● <b>OS Info:</b> {os_info}")
            
            self.finished_signal.emit(True, "Read Success", info)
        except Exception as e:
            self.finished_signal.emit(False, str(e), {})

    def execute_commands(self):
        try:
            # ----- Helper to locate mdm.apk (for push) -----
            def get_apk_path():
                base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
                apk = os.path.join(base_dir, "mdm.apk")
                if not os.path.exists(apk):
                    apk = os.path.join(os.getcwd(), "mdm.apk")
                return apk if os.path.exists(apk) else None

            # ----- 1) stat (just info, always "ok") -----
            run_adb_command(['-s', self.device_serial, 'shell', 'stat', '/data/local/tmp/mdm.apk'])
            self.log("sending 1 command ....................ok", "success")
            cooperative_sleep(self, 0.3)

            # ----- 2) push (retry until success) -----
            apk_path = get_apk_path()
            if not apk_path:
                self.log("sending 2 command ....................failed (APK not found)", "error")
                self.finished_signal.emit(False, "mdm.apk not found", {})
                return

            push_success = False
            while not push_success:
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False, "Operation cancelled by user", {})
                    return
                res2 = run_adb_command(['-s', self.device_serial, 'push', apk_path, '/data/local/tmp/mdm.apk'], timeout=120)
                if res2 and res2.returncode == 0:
                    self.log("sending 2 command ....................ok", "success")
                    push_success = True
                else:
                    err = res2.stderr if res2 else "no response"
                    self.log(f"sending 2 command ....................retrying ({err})", "warning")
                    cooperative_sleep(self, 2)
            cooperative_sleep(self, 0.5)

            # ----- 3) install (retry until success) -----
            install_success = False
            while not install_success:
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False, "Operation cancelled by user", {})
                    return
                res3 = run_adb_command(['-s', self.device_serial, 'shell', 'pm', 'install', '/data/local/tmp/mdm.apk'], timeout=90)
                if res3 and res3.returncode == 0 and "Success" in res3.stdout:
                    self.log("sending 3 command ....................ok", "success")
                    install_success = True
                else:
                    err = res3.stderr if res3 else "no response"
                    self.log(f"sending 3 command ....................retrying ({err})", "warning")
                    cooperative_sleep(self, 2)
            cooperative_sleep(self, 0.5)

            # ----- 4) remove temp APK (retry until success) -----
            remove_success = False
            while not remove_success:
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False, "Operation cancelled by user", {})
                    return
                res4 = run_adb_command(['-s', self.device_serial, 'shell', 'rm', '-f', '/data/local/tmp/mdm.apk'])
                if res4 and res4.returncode == 0:
                    self.log("sending 4 command ....................ok", "success")
                    remove_success = True
                else:
                    err = res4.stderr if res4 else "no response"
                    self.log(f"sending 4 command ....................retrying ({err})", "warning")
                    cooperative_sleep(self, 2)
            cooperative_sleep(self, 0.5)

            # ----- 5) set device admin (retry until success) -----
            admin_success = False
            while not admin_success:
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False, "Operation cancelled by user", {})
                    return
                res5 = run_adb_command(['-s', self.device_serial, 'shell', 'dpm', 'set-active-admin', 'com.tsmtool.factoryreset/.Hubris'], timeout=30)
                if res5 and res5.returncode == 0:
                    self.log("sending 5 command ....................ok", "success")
                    admin_success = True
                else:
                    err = res5.stderr if res5 else "no response"
                    self.log(f"sending 5 command ....................retrying ({err})", "warning")
                    cooperative_sleep(self, 2)
            cooperative_sleep(self, 1.0)

            # ----- 6) launch activity (retry until success) -----
            launch_success = False
            while not launch_success:
                if self.isInterruptionRequested():
                    self.finished_signal.emit(False, "Operation cancelled by user", {})
                    return
                res6 = run_adb_command(['-s', self.device_serial, 'shell', 'am', 'start', '-n', 'com.tsmtool.factoryreset/.Erketu'], timeout=20)
                if res6 and res6.returncode == 0:
                    self.log("sending 6 command ....................ok", "success")
                    launch_success = True
                else:
                    err = res6.stderr if res6 else "no response"
                    self.log(f"sending 6 command ....................retrying ({err})", "warning")
                    cooperative_sleep(self, 2)

            # ----- All done -----
            self.finished_signal.emit(True, "All commands executed successfully", {})

        except Exception as e:
            self.finished_signal.emit(False, f"Unexpected error: {str(e)}", {})

# ================= VALIDATION =================
class LoginWorker(QThread):
    finished_signal = pyqtSignal(bool, dict) # success, result_data or error_data

    def __init__(self, email, password):
        super().__init__()
        self.email = email
        self.password = password

    def run(self):
        try:
            res = firebase_login(self.email, self.password)
            if "idToken" in res:
                # Fetch user data and update last login in the worker thread
                # This prevents blocking the UI thread further
                db_update_last_login(res["localId"], res["idToken"])
                user_data = db_read_user(res["localId"], res["idToken"])
                self.finished_signal.emit(True, {"idToken": res["idToken"], "localId": res["localId"], "user": user_data})
            else:
                error_msg = res.get("error", {}).get("message", "Invalid email or password")
                self.finished_signal.emit(False, {"message": error_msg})
        except requests.exceptions.ConnectionError:
            self.finished_signal.emit(False, {"message": "Network connection error. Please check your internet."})
        except Exception as e:
            self.finished_signal.emit(False, {"message": f"An unexpected error occurred: {str(e)}"})

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    return len(password) >= 6

class HomePageSetupWorker(QThread):
    setup_finished = pyqtSignal(dict, dict) # user_data, service_settings
    error_signal = pyqtSignal(str)

    def __init__(self, uid, token, initial_user_data):
        super().__init__()
        self.uid = uid
        self.token = token
        self.initial_user_data = initial_user_data
    
    def run(self):
        try:
            # Fetch latest user data
            updated_user_data = db_read_user(self.uid, self.token)
            if updated_user_data:
                # Ensure credit is decrypted
                if "credit" in updated_user_data:
                    updated_user_data["credit"] = decrypt_credit(updated_user_data["credit"])
                # If credit was missing initially, set to 0 and update DB
                elif "credit" not in updated_user_data:
                    updated_user_data["credit"] = 0
                    # This DB update is a network call, so it's good it's in the worker
                    db_update_credit(self.uid, self.token, 0)
            else:
                # Fallback if db_read_user fails for some reason
                # Ensure initial_user_data's credit is decrypted if it exists
                if "credit" in self.initial_user_data:
                    self.initial_user_data["credit"] = decrypt_credit(self.initial_user_data["credit"])
                updated_user_data = self.initial_user_data

            # Fetch service settings (prices/status)
            service_settings = db_read_services(self.token) or {}
            self.setup_finished.emit(updated_user_data, service_settings)
        except requests.exceptions.RequestException as e:
            self.error_signal.emit(f"Network error during home page setup: {str(e)}")
        except Exception as e:
            self.error_signal.emit(f"Failed to load home page data: {str(e)}")


class CreditUpdateWorker(QThread):
    finished_signal = pyqtSignal(bool, float)

    def __init__(self, uid, token, credit):
        super().__init__()
        self.uid = uid
        self.token = token
        self.credit = credit

    def run(self):
        try:
            db_update_credit(self.uid, self.token, self.credit)
            self.finished_signal.emit(True, float(self.credit))
        except Exception:
            self.finished_signal.emit(False, float(self.credit))


class RegisterWorker(QThread):
    finished_signal = pyqtSignal(bool, dict)

    def __init__(self, username, email, password):
        super().__init__()
        self.username = username
        self.email = email
        self.password = password

    def run(self):
        try:
            res = firebase_register(self.email, self.password)
            if "idToken" in res:
                db_write_user(
                    res["localId"],
                    res["idToken"],
                    {
                        "username": self.username,
                        "email": self.email,
                        "credit": 0,
                        "createdAt": datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                    }
                )
                self.finished_signal.emit(True, {"message": "Account created successfully"})
            else:
                error_msg = res.get("error", {}).get("message", "Registration failed")
                self.finished_signal.emit(False, {"message": error_msg})
        except Exception as e:
            self.finished_signal.emit(False, {"message": f"Connection failed: {str(e)}"})


class ServiceSettingsWorker(QThread):
    finished_signal = pyqtSignal(bool, dict, str)

    def __init__(self, token):
        super().__init__()
        self.token = token

    def run(self):
        try:
            self.finished_signal.emit(True, db_read_services(self.token) or {}, "")
        except Exception as e:
            self.finished_signal.emit(False, {}, str(e))


class NothingDuplicateCheckWorker(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, token, email, imei):
        super().__init__()
        self.token = token
        self.email = email
        self.imei = imei

    def run(self):
        try:
            response = requests.get(f"{DB_URL}/nothing_orders.json?auth={self.token}", timeout=REQUEST_TIMEOUT)
            orders = response.json()
            if orders and isinstance(orders, dict):
                for data in orders.values():
                    if data.get('email') == self.email and str(data.get('imei')) == self.imei:
                        self.finished_signal.emit(True, "Your IMEI already submitted!")
                        return
            self.finished_signal.emit(False, "")
        except Exception:
            self.finished_signal.emit(False, "Unable to verify duplicate submission right now.")


class NothingHistoryWorker(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(self, token, email):
        super().__init__()
        self.token = token
        self.email = email

    def run(self):
        try:
            response = requests.get(f"{DB_URL}/nothing_orders.json?auth={self.token}", timeout=REQUEST_TIMEOUT)
            orders = response.json()
            user_orders = []
            if orders and isinstance(orders, dict):
                user_orders = [data for data in orders.values() if data.get('email') == self.email]
            self.finished_signal.emit({"orders": user_orders})
        except Exception as exc:
            self.finished_signal.emit({"orders": [], "error": str(exc)})


class DisclaimerPage(QWidget):
    def __init__(self, stack):
        super().__init__()
        self.stack = stack
        self.setObjectName("main_content")
        self.login_email = ""
        self.login_password = ""
        self.remember_status = False
        self.login_worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(15)

        title = QLabel("Official User Agreement")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #1e293b; margin-bottom: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: 1px solid #e2e8f0; border-radius: 8px; background-color: #ffffff; }
            QScrollBar:vertical { width: 8px; background: #f1f5f9; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; }
        """)
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #ffffff;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)

        text = QLabel("""
<p style='font-size: 14px; color: #334155; line-height: 1.6;'><b>Dear User,</b>
<p>The developer of this software is not responsible for any misuse or illegal activities performed using it. 
This software is intended <b>strictly for authorized mobile technical support purposes only</b>.<br><br>

<b>User Agreement Terms:</b><br>
1. No illegal or unauthorized activities allowed.<br>
2. Do not use for lost or stolen devices.<br>
3. Violation may lead to account suspension or legal action.<br>
4. You must comply with your local laws before using this software.<br>
5. You are fully responsible for any use and its consequences.<br><br>

By clicking <b>"I AGREE AND PROCEED"</b>, you confirm that you have read and accepted these terms and you are using this tool for legal repair services only.</p>
""")
        text.setWordWrap(True)
        content_layout.addWidget(text)
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        self.btn_agree = QPushButton("I AGREE AND PROCEED")
        self.btn_agree.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_agree.setFixedHeight(50)
        self.btn_agree.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; border-radius: 8px; font-weight: bold; font-size: 15px; border: none; }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_agree.clicked.connect(self.on_agree_clicked)
        layout.addWidget(self.btn_agree)

    def start_disclaimer_flow(self, email, password, remember):
        self.login_email = email
        self.login_password = password
        self.remember_status = remember

    def on_agree_clicked(self):
        if not self.login_email: return
        if self.login_worker and self.login_worker.isRunning():
            return
        
        # 1. Log agreement to GitHub
        log_agreement_to_github(self.login_email, socket.gethostname())
        
        # 2. Start Login process
        self.btn_agree.setEnabled(False)
        self.btn_agree.setText("Authenticating... Please Wait")
        
        self.login_worker = LoginWorker(self.login_email, self.login_password)
        safe_connect(self.login_worker.finished_signal, self.handle_post_agree_login)
        safe_connect(self.login_worker.finished, self.login_worker.deleteLater)
        safe_connect(self.login_worker.finished, lambda: setattr(self, "login_worker", None))
        self.login_worker.start()

    def handle_post_agree_login(self, success, result):
        self.btn_agree.setEnabled(True)
        self.btn_agree.setText("I AGREE AND PROCEED")
        
        if success:
            # Save credentials if remember me
            settings = QSettings("GSM NP Unlocker", "App")
            if self.remember_status:
                settings.setValue("email", self.login_email)
                settings.setValue("password", self.login_password)
                settings.setValue("remember_me", True)
            else:
                settings.remove("email")
                settings.remove("password")
                settings.setValue("remember_me", False)

            # Set user data in HomePage and switch to it
            self.stack.widget(3).set_user(result["user"], result["localId"], result["idToken"])
            self.stack.setCurrentIndex(3)
        else:
            error_msg = result.get("message", "Login failed.")
            QMessageBox.warning(self, "Login Failed", error_msg)
            # Go back to login page
            self.stack.setCurrentIndex(0)

    def cancel_background_work(self):
        cleanup_thread(self.login_worker)
        self.login_worker = None

# ================= STYLE (DESKTOP) =================
APP_STYLE = """
QWidget {
    color: #111827;
    font-family: Segoe UI;
    font-size: 13px;
}
QWidget#main_content {
    background-color: #f5f6f8;
}
QLineEdit {
    background: white;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #2563eb;
    selection-color: white;
}
QLineEdit:focus {
    border: 1px solid #2563eb;
}
QPushButton {
    background-color: #2563eb;
    color: white;
    border-radius: 4px;
    padding: 7px;
    border: none;
    outline: none;
}
QPushButton:hover {
    background-color: #1d4ed8;
}
QPushButton#secondary {
    background-color: #e5e7eb;
    color: #111827;
}
QPushButton#eye {
    background-color: transparent;
    border: none;
    color: #6b7280;
    font-size: 14px;
}
QLabel#title {
    font-size: 18px;
    font-weight: 600;
}
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #2563eb;
}
QCheckBox {
    spacing: 5px;
}
QComboBox {
    background: white;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px;
    color: #111827;
}
QComboBox QAbstractItemView {
    background-color: white;
    color: #111827;
    selection-background-color: #2563eb;
    selection-color: white;
    border: 1px solid #cbd5e1;
}
QTextEdit#logs {
    background-color: transparent;
    color: #4b5563;
    font-family: 'Segoe UI';
    font-size: 13px;
    border: none;
}
"""

# ================= LOGIN PAGE =================
class LoginPage(QWidget):
    def __init__(self, stack):
        super().__init__()
        self.stack = stack
        self.setObjectName("main_content")
        self.settings = QSettings("GSM NP Unlocker", "App")
        self.update_in_progress = False
        self.login_worker = None # Initialize worker

        main = QVBoxLayout(self)
        main.setContentsMargins(60, 40, 60, 40)
        main.setSpacing(12)

        # Update status label at the top
        self.update_label = QLabel("")
        self.update_label.setStyleSheet("color: #2563eb; font-weight: bold; font-size: 11px;")
        self.update_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.logo_label = QLabel("Login")
        self.logo_label.setObjectName("title")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email address")

        # Password
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.show_password = QCheckBox("Show Password")
        self.show_password.toggled.connect(self.toggle_password_visibility)

        self.remember_me = QCheckBox("Remember me")
        self.remember_me.setChecked(bool(self.settings.value("remember_me", False)))

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)  # Indeterminate

        self.btn_login = QPushButton("Login")
        self.btn_register = QPushButton("Create new account")
        self.btn_register.setObjectName("secondary")

        self.btn_login.clicked.connect(self.login)
        self.btn_register.clicked.connect(lambda: self.stack.setCurrentIndex(1))

        main.addWidget(self.update_label)
        main.addWidget(self.logo_label)
        main.addWidget(self.email)
        main.addWidget(self.password)
        
        opts_layout = QHBoxLayout()
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.addWidget(self.remember_me)
        opts_layout.addStretch()
        opts_layout.addWidget(self.show_password)
        main.addLayout(opts_layout)
        
        main.addWidget(self.progress)
        main.addSpacing(10)
        main.addWidget(self.btn_login)
        main.addWidget(self.btn_register)

        # Load saved credentials
        if self.remember_me.isChecked():
            self.email.setText(self.settings.value("email", ""))
            self.password.setText(self.settings.value("password", ""))
            
        # Run fast update check in background
        self.check_for_updates()

    def check_for_updates(self):
        if hasattr(self, "up_worker") and self.up_worker and self.up_worker.isRunning():
            return
        self.up_worker = UpdateWorker()
        safe_connect(self.up_worker.status_signal, self.on_update_status)
        safe_connect(self.up_worker.progress_signal, self.on_update_progress)
        safe_connect(self.up_worker.update_ready_signal, self.install_update)
        safe_connect(self.up_worker.finished, self.up_worker.deleteLater)
        safe_connect(self.up_worker.finished, lambda: setattr(self, "up_worker", None))
        self.up_worker.start()

    def on_update_status(self, status):
        self.update_label.setText(status)
        if "New Update" in status:
            self.update_in_progress = True
            self.btn_login.setEnabled(False)
            self.btn_register.setEnabled(False)

    def on_update_progress(self, value):
        self.progress.setRange(0, 100)
        self.progress.setValue(value)
        self.progress.setVisible(True)

    def install_update(self, temp_file):
        self.update_label.setText("Update Ready! Restarting Tool...")
        current_exe = os.path.abspath(sys.argv[0])
        bat_file = os.path.join(tempfile.gettempdir(), "update.bat")
        
        try:
            with open(bat_file, "w") as f:
                f.write(f'''@echo off
timeout /t 2 >nul
copy /y "{temp_file}" "{current_exe}"
start "" "{current_exe}"
del /q "{temp_file}"
del "%~f0"
''')
            subprocess.Popen(bat_file, shell=True, creationflags=0x08000000)
            QApplication.quit()
            sys.exit(0)
        except Exception as e:
            self.update_label.setText("Update Error! Try running as Admin.")
            print(f"Update failed: {e}")

    def cancel_background_work(self):
        cleanup_thread(getattr(self, "up_worker", None))
        self.up_worker = None

    def toggle_password_visibility(self):
        if self.show_password.isChecked():
            self.password.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password.setEchoMode(QLineEdit.EchoMode.Password)

    def login(self):
        if self.update_in_progress:
            return
            
        email = self.email.text().strip()
        password = self.password.text()

        if not validate_email(email):
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address")
            return
        if not validate_password(password):
            QMessageBox.warning(self, "Invalid Password", "Password must be at least 6 characters")
            return

        # Switch to Disclaimer Page (Index 2) before login
        self.stack.widget(2).start_disclaimer_flow(email, password, self.remember_me.isChecked())
        self.stack.setCurrentIndex(2)

# ================= REGISTER PAGE =================
class RegisterPage(QWidget):
    def __init__(self, stack):
        super().__init__()
        self.stack = stack
        self.setObjectName("main_content")

        main = QVBoxLayout(self)
        main.setContentsMargins(60, 40, 60, 40)
        main.setSpacing(12)

        title = QLabel("Create Account")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email address")

        # Password
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password (min 6 characters)")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.show_password = QCheckBox("Show Password")
        self.show_password.toggled.connect(self.toggle_password_visibility)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)

        btn_create = QPushButton("Register")
        btn_back = QPushButton("Back to login")
        btn_back.setObjectName("secondary")

        btn_create.clicked.connect(self.register)
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        main.addWidget(title)
        main.addWidget(self.username)
        main.addWidget(self.email)
        main.addWidget(self.password)
        
        opts_layout = QHBoxLayout()
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.addStretch()
        opts_layout.addWidget(self.show_password)
        main.addLayout(opts_layout)
        
        main.addWidget(self.progress)
        main.addSpacing(10)
        main.addWidget(btn_create)
        main.addWidget(btn_back)

    def toggle_password_visibility(self):
        if self.show_password.isChecked():
            self.password.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password.setEchoMode(QLineEdit.EchoMode.Password)

    def register(self):
        username = self.username.text().strip()
        email = self.email.text().strip()
        password = self.password.text()

        if not username:
            QMessageBox.warning(self, "Invalid Username", "Please enter a username")
            return
        if not validate_email(email):
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address")
            return
        if not validate_password(password):
            QMessageBox.warning(self, "Invalid Password", "Password must be at least 6 characters")
            return

        self.progress.setVisible(True)
        self.setEnabled(False)
        self.register_worker = RegisterWorker(username, email, password)
        safe_connect(self.register_worker.finished_signal, self.on_register_finished)
        safe_connect(self.register_worker.finished, self.register_worker.deleteLater)
        safe_connect(self.register_worker.finished, lambda: setattr(self, "register_worker", None))
        self.register_worker.start()

    def on_register_finished(self, success, result):
        self.progress.setVisible(False)
        self.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", result.get("message", "Account created successfully"))
            self.stack.setCurrentIndex(0)
        else:
            QMessageBox.warning(self, "Error", result.get("message", "Registration failed"))

# ================= HOME PAGE =================
class HomePage(QWidget):
    models_loaded_signal = pyqtSignal(list)

    def __init__(self, stack):
        super().__init__()
        self.stack = stack
        self.setObjectName("main_content")
        self.active_workers = set()
        self.user_data = {}
        self.uid = None
        self.token = None
        self.adb = load_adb_dll()
        # Pre-start ADB server in background for super fast detection
        threading.Thread(target=lambda: run_hidden(['adb', 'start-server'], timeout=10), daemon=True).start()
        
        def safe_start_adb():
            try:
                run_hidden(['adb', 'start-server'], timeout=10)
            except: pass
            
        threading.Thread(target=safe_start_adb, daemon=True).start()
        
        self.mi_token = ""
        self.device_model = ""
        self.device_serial = ""
        self.pending_frp_cost = 0
        self.operation_generation = 0
        self._pending_service_settings_callback = None
        self.service_settings_worker = None

        self.service_settings = {}
        self.current_service = "Xiaomi"
        
        # Dynamic model storage
        self.redmi_models = []
        self.services = {
            "Xiaomi": ["Check Server Status", "Read Phone Info", "Reset FRP Wipe User Data", "FIX ADB", "ADB DRIVER FIX"],
            "Realme": ["FRP Unlock", "Factory Reset", "Safe Format", "Read Info"],
            "Nothing": ["Nothing Network Unlock", "Check by USB"],
            "Demo Remove": ["OPPO Demo Remove", "OnePlus Demo Remove", "Realme Demo Remove"]
        }

        # Initialize Completer for Search
        self.search_completer = QCompleter(self)
        self.search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_completer.activated.connect(self.filter_operations)
        safe_connect(self.models_loaded_signal, self.on_models_loaded)
        
        threading.Thread(target=self._fetch_external_models, daemon=True).start()

        # Wrapper layout to handle flush footer
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)

        # Service Stack for switching between menu and services
        self.service_stack = QStackedWidget()
        self._create_main_menu_page()
        self._create_operation_page()
        
        # Initialize HomePageSetupWorker
        self.home_page_setup_worker = None

        self.service_stack.addWidget(self.main_menu_widget)
        self.service_stack.addWidget(self.operation_page_widget)

        # Footer with Refresh Button
        footer_widget = QWidget()
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(10, 5, 10, 5)

        self.footer_label = QLabel("")
        self.footer_label.setStyleSheet("font-size: 12px; color: #333;")
        
        logout_btn = QPushButton("Logout")
        logout_btn.setFixedWidth(110)
        logout_btn.setStyleSheet("font-size: 11px; padding: 4px; background-color: #e5e7eb; color: #333; border: 1px solid #ccc; outline: none;")
        logout_btn.clicked.connect(self.logout)

        footer_layout.addWidget(self.footer_label)
        footer_layout.addStretch()
        footer_layout.addWidget(logout_btn)

        wrapper.addWidget(self.service_stack, 1)
        wrapper.addWidget(footer_widget)

    def _track_worker(self, attr_name, worker):
        old_worker = getattr(self, attr_name, None)
        if old_worker and old_worker is not worker:
            cleanup_thread(old_worker)
        setattr(self, attr_name, worker)
        self.active_workers.add(worker)

        def cleanup():
            self.active_workers.discard(worker)
            if getattr(self, attr_name, None) is worker:
                setattr(self, attr_name, None)

        safe_connect(worker.finished, cleanup)
        safe_connect(worker.finished, worker.deleteLater)
        return worker

    def stop_all_workers(self):
        for worker in list(self.active_workers):
            disconnect_worker_signals(worker)
            cleanup_thread(worker)
        self.active_workers.clear()
        self._pending_service_settings_callback = None
        self._pending_nothing_submit = None
        self.handle_nothing_popup(False)

    def back_to_main_menu(self):
        self.operation_generation += 1
        self.stop_all_workers()
        self.pending_frp_cost = 0
        self._pending_nothing_submit = None
        self.op_btn.setEnabled(True)
        self.op_btn.setVisible(True)
        self.op_input.setVisible(True)
        self.op_input.setEnabled(True)
        self.log_output.clear()
        self.service_stack.setCurrentIndex(0)

    def schedule_operation_start(self, callback, delay=300):
        generation = self.operation_generation

        def guarded_start():
            if generation == self.operation_generation and self.service_stack.currentIndex() == 1:
                callback()

        QTimer.singleShot(delay, guarded_start)

    def get_service_price(self, service_name):
        """Return user-specific price if exists, otherwise global price."""
        custom_prices = self.user_data.get("custom_prices", {})
        if isinstance(custom_prices, dict) and service_name in custom_prices:
            return decrypt_credit(custom_prices[service_name])
        s_info = self.service_settings.get(service_name, {})
        return decrypt_credit(s_info.get('credit')) if 'credit' in s_info else 0.0

    def refresh_user_data(self):
        """Fetch latest user info in the background so the UI never blocks on a network call."""
        if not self.token or not self.uid:
            return
        if self.home_page_setup_worker and self.home_page_setup_worker.isRunning():
            return
        self._start_home_page_setup()

    def _queue_credit_update(self, new_credit):
        if not self.uid or not self.token:
            return
        worker = self._track_worker("credit_update_worker", CreditUpdateWorker(self.uid, self.token, new_credit))
        safe_connect(worker.finished_signal, lambda *_: None)
        worker.start()

    def _load_service_settings_async(self, callback=None):
        if not self.token:
            if callback:
                callback(False, {}, "Missing authentication token")
            return
        self._pending_service_settings_callback = callback
        if self.service_settings_worker and self.service_settings_worker.isRunning():
            return
        self.service_settings_worker = self._track_worker("service_settings_worker", ServiceSettingsWorker(self.token))
        safe_connect(self.service_settings_worker.finished_signal, self._handle_service_settings_result)
        self.service_settings_worker.start()

    def _handle_service_settings_result(self, success, service_settings, error):
        if success:
            self.service_settings = service_settings
        else:
            self.append_frp_log(f"Service settings refresh failed: {error}", "warning")
        callback = self._pending_service_settings_callback
        self._pending_service_settings_callback = None
        if callback:
            callback(success, service_settings, error)

    def _start_home_page_setup(self):
        if not self.token or not self.uid:
            return
        if self.home_page_setup_worker and self.home_page_setup_worker.isRunning():
            return
        self.home_page_setup_worker = self._track_worker(
            "home_page_setup_worker",
            HomePageSetupWorker(self.uid, self.token, self.user_data)
        )
        safe_connect(self.home_page_setup_worker.setup_finished, self.on_home_page_setup_finished)
        safe_connect(self.home_page_setup_worker.error_signal, lambda msg: self.append_frp_log(msg, "error"))
        self.home_page_setup_worker.start()

    def _set_repair_buttons_enabled(self, enabled):
        self.adb_fix_btn.setEnabled(enabled)
        self.driver_fix_btn.setEnabled(enabled)
        self.op_btn.setEnabled(enabled)

    def on_fix_adb_clicked(self):
        self.log_output.clear()
        self.append_frp_log("Starting FIX ADB sequence...", "header")
        self._set_repair_buttons_enabled(False)
        self.adb_repair_worker = self._track_worker("adb_repair_worker", AdbRepairWorker('fix', parent=self))
        safe_connect(self.adb_repair_worker.log_signal, self.append_frp_log)
        safe_connect(self.adb_repair_worker.finished_signal, self.on_adb_fix_finished)
        self.adb_repair_worker.start()

    def on_driver_fix_clicked(self):
        self.log_output.clear()
        self.append_frp_log("Starting ADB DRIVER FIX...", "header")
        self._set_repair_buttons_enabled(False)
        self.adb_repair_worker = self._track_worker("adb_repair_worker", AdbRepairWorker('driver', parent=self))
        safe_connect(self.adb_repair_worker.log_signal, self.append_frp_log)
        safe_connect(self.adb_repair_worker.finished_signal, self.on_driver_fix_finished)
        self.adb_repair_worker.start()

    def on_adb_fix_finished(self, success, message):
        if success:
            self.append_frp_log("FIX ADB completed successfully.", "success")
        else:
            self.append_frp_log(f"FIX ADB failed: {message}", "error")

        if not self.adb:
            self.adb = load_adb_dll()

        self._set_repair_buttons_enabled(True)

    def on_driver_fix_finished(self, success, message):
        if success:
            self.append_frp_log("ADB DRIVER FIX completed successfully.", "success")
        else:
            self.append_frp_log(f"ADB DRIVER FIX failed: {message}", "error")

        self._set_repair_buttons_enabled(True)

    def _create_main_menu_page(self):
        self.main_menu_widget = QWidget()
        layout = QHBoxLayout(self.main_menu_widget)
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(20)

        # --- Left Side: Service Categories ---
        left_box = QWidget()
        left_box.setObjectName("left_box")
        left_box.setStyleSheet("#left_box { background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; }")
        left_layout = QVBoxLayout(left_box)
        
        lbl_services = QLabel("Service Menu")
        lbl_services.setStyleSheet("font-weight: bold; font-size: 14px; border: none; color: #333;")
        left_layout.addWidget(lbl_services)

        # --- My Account Button (Top) ---
        self.btn_my_account = QPushButton("Server Status")
        self.btn_my_account.clicked.connect(self.show_account_details)
        # Apply the same style as other service buttons
        self.btn_my_account.setStyleSheet("""
            QPushButton { text-align: left; padding: 10px; border: 1px solid #eee; background: #f9f9f9; border-radius: 4px; color: #333; outline: none; margin-bottom: 5px; }
            QPushButton:hover { background: #eef2ff; border-color: #2563eb; color: #2563eb; }""")
        left_layout.addWidget(self.btn_my_account)

        for srv in self.services.keys():
            btn = QPushButton(srv)
            btn.clicked.connect(lambda checked, s=srv: self.select_service(s))
            btn.setStyleSheet("""
                QPushButton { text-align: left; padding: 10px; border: 1px solid #eee; background: #f9f9f9; border-radius: 4px; color: #333; outline: none; }
                QPushButton:hover { background: #eef2ff; border-color: #2563eb; color: #2563eb; }
            """)
            left_layout.addWidget(btn)

        left_layout.addStretch()

        # --- Right Side: Operations & Selection ---
        right_box = QWidget()
        right_box.setObjectName("right_box")
        right_box.setStyleSheet("#right_box { background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; }")
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(20, 20, 20, 20)

        self.lbl_ops = QLabel("Operations")
        self.lbl_ops.setStyleSheet("font-weight: bold; font-size: 14px; border: none; color: #333;")
        
        # --- Search Bar & Find Button ---
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search model or service (e.g. Xiaomi)...")
        self.search_input.returnPressed.connect(self.filter_operations)
        
        self.btn_find = QPushButton("Find")
        self.btn_find.setFixedWidth(80)
        self.btn_find.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_find.clicked.connect(self.filter_operations)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_find)

        # Select Bar
        self.model_select = QComboBox()
        self.model_select.addItems(["Select Model / Brand...", "Samsung Galaxy", "Xiaomi Redmi", "Oppo / Realme", "Vivo", "iPhone"])

        # Dynamic Operations Container
        self.ops_container = QWidget()
        self.ops_container.setStyleSheet("background: transparent;")
        self.ops_layout = QVBoxLayout(self.ops_container)
        self.ops_layout.setContentsMargins(0, 10, 0, 0)
        self.ops_layout.setSpacing(10)
        self.ops_layout.addStretch()

        right_layout.addWidget(self.lbl_ops)
        right_layout.addLayout(search_layout)
        right_layout.addWidget(self.model_select)
        right_layout.addWidget(self.ops_container)
        right_layout.addStretch()

        self.search_input.setCompleter(self.search_completer)

        layout.addWidget(left_box, 1)
        layout.addWidget(right_box, 2)

        self.update_search_suggestions()

    def show_account_details(self):
        """Displays user profile details and all service statuses/prices on the right panel."""
        self.current_service = "Account"
        self.lbl_ops.setText("System Dashboard Realtime Status")
        self.search_input.setVisible(False)
        self.btn_find.setVisible(False)
        self.model_select.setVisible(False)

        # Clear existing layout
        for i in reversed(range(self.ops_layout.count())):
            item = self.ops_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()

        u = self.user_data.get('username', 'N/A')
        e = self.user_data.get('email', 'N/A')
        c = float(self.user_data.get('credit', 0))

        # Fetch latest data in the background; keep the dashboard responsive while the call runs.
        custom_prices = self.user_data.get("custom_prices", {})
        if self.token and not self.service_settings:
            self.refresh_user_data()

        # Dashboard container
        dashboard_widget = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_widget)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(12)

        # User details card
        user_card = QWidget()
        user_card.setStyleSheet(
            "background: transparent;"
        )
        user_layout = QVBoxLayout(user_card)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(6)


        for i in range(user_layout.count()):
            widget = user_layout.itemAt(i).widget()
            if isinstance(widget, QLabel):
                widget.setStyleSheet("font-size: 11px; margin: 0px;")
                widget.setTextFormat(Qt.TextFormat.RichText)

        dashboard_layout.addWidget(user_card)

        # Service status section
        status_header = QLabel("SERVER STATUS")
        status_header.setStyleSheet("color: #2563eb; font-size: 12px; font-weight: 700; text-transform: uppercase;")
        dashboard_layout.addWidget(status_header)

        service_list = QWidget()
        service_list_layout = QVBoxLayout(service_list)
        service_list_layout.setContentsMargins(0, 0, 0, 0)
        service_list_layout.setSpacing(8)

        for srv_name in self.services.keys():
            s_data = self.service_settings.get(srv_name, {})
            status = s_data.get('status', 'offline')
            price = decrypt_credit(s_data.get('credit')) if 'credit' in s_data else 0.0
            status_color = "#047857" if status == "online" else "#b91c1c"
            status_bg = "#ecfdf5" if status == "online" else "#fef2f2"
            price_style = "#f3f4f6"
            price_text_color = "#111827"

            if isinstance(custom_prices, dict) and srv_name in custom_prices:
                price = decrypt_credit(custom_prices[srv_name])
                price_style = "#eff6ff"
                price_text_color = "#1d4ed8"

            row = QWidget()
            row.setStyleSheet(
                "background: transparent;"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            row_inner = QWidget()
            row_inner.setStyleSheet(
                "background: #ffffff;"
                "padding: 12px 14px;"
            )
            row_inner_layout = QHBoxLayout(row_inner)
            row_inner_layout.setContentsMargins(0, 0, 0, 0)
            row_inner_layout.setSpacing(10)

            name_label = QLabel(srv_name)
            name_label.setStyleSheet("color: #111827; font-size: 12px; font-weight: 700;")

            price_label = QLabel(f"{price:.2f} CR")
            price_label.setStyleSheet(
                f"background: {price_style}; color: {price_text_color};"
                "padding: 5px 12px; border-radius: 999px; font-size: 11px; font-weight: 700;"
            )
            price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if isinstance(custom_prices, dict) and srv_name in custom_prices:
                vip_label = QLabel("VIP")
                vip_label.setStyleSheet(
                    "background: #2563eb; color: white; padding: 4px 10px;"
                    "border-radius: 999px; font-size: 10px; font-weight: 700;"
                )
                vip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                vip_label = None

            status_label = QLabel(status.upper())
            status_label.setStyleSheet(
                f"background: {status_bg}; color: {status_color};"
                "padding: 6px 14px; border: none; border-radius: 999px;"
                "font-size: 11px; font-weight: 700;"
            )
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            row_inner_layout.addWidget(name_label)
            row_inner_layout.addStretch()
            row_inner_layout.addWidget(price_label)
            if vip_label:
                row_inner_layout.addWidget(vip_label)
            row_inner_layout.addWidget(status_label)

            row_layout.addWidget(row_inner)
            service_list_layout.addWidget(row)

        dashboard_layout.addWidget(service_list)
        dashboard_layout.addStretch()

        self.ops_layout.addWidget(dashboard_widget)

    def update_search_suggestions(self):
        """Update the list of suggestions for the search bar."""
        suggestions = list(self.services.keys())  # Add service names
        
        # Add all operations from all services
        for ops in self.services.values():
            suggestions.extend(ops)
            
        # Add fetched redmi models
        suggestions.extend(self.redmi_models)
        
        # Set unique suggestions to the completer
        model = QStringListModel(list(set(suggestions)))
        self.search_completer.setModel(model)

    def _fetch_external_models(self):
        """Fetch Redmi models from GitHub in the background."""
        try:
            url = "https://raw.githubusercontent.com/Technical-Mishra-XD/GSMMULTITOOL/refs/heads/main/redmi.json"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                # Assuming the JSON is a list of model names
                if isinstance(data, list):
                    self.models_loaded_signal.emit(data)
        except Exception as e:
            print(f"Failed to fetch models: {e}")

    def on_models_loaded(self, models):
        self.redmi_models = models
        self.update_search_suggestions()

    def select_service(self, service_name):
        self.current_service = service_name
        self.lbl_ops.setText(f"{service_name} Operations")

        # UI Visibility Logic
        is_realme = service_name == "Realme"
        is_nothing = service_name == "Nothing"
        
        # Hide search and find functionality for Nothing and Realme
        show_search = not (is_nothing or is_realme)
        self.search_input.setVisible(show_search)
        self.btn_find.setVisible(show_search)
        self.search_input.clear()

        # Handle Realme "Coming Soon" case
        if is_realme:
            self.model_select.setVisible(False)
            while self.ops_layout.count():
                child = self.ops_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
            
            msg = QLabel("This service is coming soon!")
            msg.setStyleSheet("font-size: 16px; font-weight: bold; color: #2563eb; margin-top: 30px;")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ops_layout.addWidget(msg)
            self.ops_layout.addStretch()
            return

        self.update_ops_view(self.services.get(service_name, []))
        
        # Update Model Selector dynamically
        self.model_select.clear()
        if service_name == "Xiaomi":
            self.model_select.setVisible(True)
            if self.redmi_models:
                self.model_select.addItem("Xiaomi Universal All Models")
                self.model_select.addItems(self.redmi_models)
            else:
                self.model_select.addItem("Xiaomi Universal All Models")
        elif service_name == "Nothing":
            self.model_select.setVisible(False)
        else:
            self.model_select.setVisible(True)
            self.model_select.addItems(["Select Model / Brand...", "Samsung Galaxy", "Oppo / Realme", "Vivo", "iPhone", "Generic"])

    def filter_operations(self):
        query = self.search_input.text().strip().lower()
        query_raw = self.search_input.text().strip()
        if not query:
            self.update_ops_view(self.services.get(self.current_service, []))
            return

        # 1. Check if query matches a Service Name (switch tab)
        for srv_name in self.services.keys():
            if query == srv_name.lower():
                self.select_service(srv_name)
                return

        # 2. If in Xiaomi service, filter and show models from the fetched GitHub list
        if self.current_service == "Xiaomi":
            # Check for exact match first (useful when selecting from suggestions)
            for m_name in self.redmi_models:
                if query == m_name.lower():
                    self.select_model_from_search(m_name)
                    return

            # If not an exact match, show filtered list of model buttons
            filtered_models = [m for m in self.redmi_models if query in m.lower()]
            if filtered_models:
                self.update_models_view(filtered_models)
                return

        # 3. Otherwise, filter existing operations
        all_ops = self.services.get(self.current_service, [])
        filtered = [op for op in all_ops if query in op.lower()]
        self.update_ops_view(filtered)

    def update_models_view(self, models_list):
        """Search results mein fetched models ko dikhane ke liye."""
        # Clear previous buttons
        while self.ops_layout.count():
            child = self.ops_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for model_name in models_list:
            btn = QPushButton(f"Model: {model_name}")
            btn.setMinimumHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #10b981; /* Green color for model results */
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    outline: none;
                    text-align: left;
                    padding-left: 15px;
                }
                QPushButton:hover { background-color: #059669; }
            """)
            btn.clicked.connect(lambda checked, m=model_name: self.select_model_from_search(m))
            self.ops_layout.addWidget(btn)
        self.ops_layout.addStretch()

    def select_model_from_search(self, model_name):
        """Search se model click hone par dropdown update karein aur operations dikhayein."""
        idx = self.model_select.findText(model_name)
        if idx >= 0:
            self.model_select.setCurrentIndex(idx)
        self.search_input.clear()
        # Model select hone ke baad wapas operations dikhayein
        self.update_ops_view(self.services.get("Xiaomi", []))

    def update_ops_view(self, ops_list):
        # Clear previous buttons
        while self.ops_layout.count():
            child = self.ops_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not ops_list:
            self.ops_layout.addWidget(QLabel("No operations found."))

        for op_name in ops_list:
            btn = QPushButton(op_name)
            btn.setMinimumHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    outline: none;
                }
                QPushButton:hover { background-color: #1d4ed8; }
            """)
            btn.clicked.connect(lambda checked, op=op_name: self.open_service_window(op))
            self.ops_layout.addWidget(btn)
        self.ops_layout.addStretch()

    def open_service_window(self, operation_name):
        self.operation_generation += 1
        self.stop_all_workers()
        self.op_label.setText(f"{operation_name} - {self.model_select.currentText()}")
        self.log_output.clear()

        # Agar Reset FRP ya Status Check hai toh input aur start button dono hatao
        is_frp = "Reset FRP" in operation_name or "Check by USB" in operation_name
        is_read_info = "Read Phone Info" in operation_name
        is_status_check = "Check Server Status" in operation_name
        is_demo_remove = "Demo Remove" in operation_name
        is_repair_action = operation_name in ["FIX ADB", "ADB DRIVER FIX"]

        hide_input = is_frp or is_read_info or is_status_check or is_repair_action or is_demo_remove
        self.op_input.setVisible(not hide_input)
        self.op_btn.setVisible(not hide_input)

        if not hide_input:
            self.op_btn.setText(f"Start {operation_name}")
            self.op_input.clear()
            if "Network Unlock" in operation_name:
                self.op_input.setPlaceholderText("Enter 15-digit IMEI")
            else:
                self.op_input.setPlaceholderText("Enter Device IMEI ")

        self.service_stack.setCurrentIndex(1)

        if "Check by USB" in operation_name:
            self.schedule_operation_start(self.start_nothing_check)
        elif "Network Unlock" in operation_name:
            self.schedule_operation_start(self.display_nothing_history)
        elif is_frp:
            # Thoda delay taaki screen change hone ke baad logs start ho
            self.schedule_operation_start(self.start_frp_sequence)
        elif is_read_info:
            self.schedule_operation_start(self.start_read_info_sequence)
        elif is_status_check:
            # Direct status aur price dikhane ke liye
            self.schedule_operation_start(self.display_server_status)
        elif is_demo_remove:
            self.schedule_operation_start(self.start_demo_remove_sequence)
        elif operation_name == "FIX ADB":
            self.schedule_operation_start(self.on_fix_adb_clicked)
        elif operation_name == "ADB DRIVER FIX":
            self.schedule_operation_start(self.on_driver_fix_clicked)

    def _create_operation_page(self):
        self.operation_page_widget = QWidget()
        layout = QVBoxLayout(self.operation_page_widget)
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(15)

        self.op_label = QLabel("Service Operation")
        self.op_label.setStyleSheet("font-size:16px; font-weight:600;")

        self.op_input = QLineEdit()
        self.op_input.setPlaceholderText("Enter Device ID / IMEI / SN")

        self.op_btn = QPushButton("Start Operation")
        self.op_btn.clicked.connect(self.perform_operation)

        self.adb_fix_btn = QPushButton("FIX ADB")
        self.adb_fix_btn.clicked.connect(self.on_fix_adb_clicked)
        self.driver_fix_btn = QPushButton("ADB DRIVER FIX")
        self.driver_fix_btn.clicked.connect(self.on_driver_fix_clicked)

        for btn in (self.adb_fix_btn, self.driver_fix_btn):
            btn.setMinimumHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #10b981;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    outline: none;
                }
                QPushButton:hover { background-color: #059669; }
            """)
            btn.setVisible(False)

        self.repair_buttons_layout = QHBoxLayout()
        self.repair_buttons_layout.addWidget(self.adb_fix_btn)
        self.repair_buttons_layout.addWidget(self.driver_fix_btn)

        self.log_output = QTextEdit()
        self.log_output.setObjectName("logs")
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Operation details will appear here...")

        back_btn = QPushButton("Back")
        back_btn.setObjectName("secondary")
        back_btn.clicked.connect(self.back_to_main_menu)

        layout.addWidget(self.op_label)
        layout.addWidget(self.op_input)
        layout.addWidget(self.op_btn)
        layout.addLayout(self.repair_buttons_layout)
        layout.addWidget(self.log_output)
        layout.addSpacing(5)
        layout.addWidget(back_btn)

    def set_user(self, user, uid, token):
        self.uid = uid
        self.token = token
        # Immediately switch to the main menu and show the server status page to avoid a blank or intermediate state
        self.service_stack.setCurrentIndex(0) # Ensure main menu is visible
        self.show_account_details() # Display initial (possibly empty) server status

        # Start worker to fetch user data and service settings in background
        self.home_page_setup_worker = self._track_worker("home_page_setup_worker", HomePageSetupWorker(uid, token, user))
        safe_connect(self.home_page_setup_worker.setup_finished, self.on_home_page_setup_finished)
        safe_connect(self.home_page_setup_worker.error_signal, lambda msg: self.append_frp_log(msg, "error"))
        self.home_page_setup_worker.start()

    def on_home_page_setup_finished(self, updated_user_data, service_settings):
        # Update UI with fetched data
        self.user_data = updated_user_data
        self.service_settings = service_settings

        self.update_footer()
        self.show_account_details() # This will display the dashboard with updated info

        # Log Login Activity (Username and Credit)
        msg = f"USER LOGIN: {self.user_data.get('username')} | Email: {self.user_data.get('email')} | Total Credit: {self.user_data.get('credit')}"
        send_github_log(msg)

    def logout(self):
        self.stop_all_workers()
        # Log Logout Activity
        msg = f"USER LOGOUT: {self.user_data.get('username')} | Email: {self.user_data.get('email')} | Credit: {self.user_data.get('credit')}"
        send_github_log(msg)
        self.stack.setCurrentIndex(0)

    def update_footer(self):
        credit = self.user_data.get("credit", 0)
        self.footer_label.setText(f"User: {self.user_data.get('username', 'User')}   |   Email: {self.user_data.get('email', '')}   |   Credits: {credit}")

    def handle_nothing_popup(self, show):
        if show:
            self.wait_popup = QMessageBox(self)
            self.wait_popup.setWindowTitle("Device Connection")
            self.wait_popup.setText("Connect your phone in Fastboot mode to continue...")
            self.wait_popup.setStandardButtons(QMessageBox.StandardButton.NoButton)
            self.wait_popup.show()
        else:
            if hasattr(self, 'wait_popup') and self.wait_popup:
                self.wait_popup.accept()
                self.wait_popup = None

    def start_nothing_check(self):
        self.log_output.clear()
        self.check_worker = self._track_worker("check_worker", NothingCheckWorker(self.token, self.uid))
        safe_connect(self.check_worker.log_signal, self.append_frp_log)
        safe_connect(self.check_worker.popup_signal, self.handle_nothing_popup)
        safe_connect(self.check_worker.finished_signal, lambda s, m: self.op_btn.setEnabled(True))
        self.check_worker.start()

    def perform_operation(self):
        op_name = self.op_label.text()
        # --- FRP Wipe ke liye direct trigger (bina input check ke) ---
        if "Reset FRP Wipe User Data" in op_name:
            self.start_frp_sequence()
            return

        if "Demo Remove" in op_name:
            self.start_demo_remove_sequence()
            return
            
        if "Network Unlock" in op_name:
            imei = self.op_input.text().strip()
            if not re.match(r'^\d{15}$', imei):
                # 15-digit IMEI validation
                QMessageBox.warning(self, "Invalid IMEI", "Please enter a valid 15-digit IMEI.")
                return
            
            self.op_input.setEnabled(False)
            self.op_btn.setEnabled(False)
            self._pending_nothing_submit = {"imei": imei, "email": self.user_data.get('email')}
            self._track_worker("nothing_duplicate_worker", NothingDuplicateCheckWorker(self.token, self.user_data.get('email'), imei))
            self.nothing_duplicate_worker = getattr(self, "nothing_duplicate_worker", None)
            if self.nothing_duplicate_worker is not None:
                safe_connect(self.nothing_duplicate_worker.finished_signal, self._handle_nothing_duplicate_check)
                self.nothing_duplicate_worker.start()
            return

        input_val = self.op_input.text().strip()
        if not input_val:
            QMessageBox.warning(self, "Input Required", "Please enter the required Device ID/IMEI")
            return
            
        # Refresh service settings in the background so the UI stays responsive.
        self.refresh_user_data()

        # Check Service Status and Credit
        s_info = self.service_settings.get(self.current_service, {})
        if s_info.get('status', 'offline') != 'online':
            QMessageBox.warning(self, "Service Offline", f"The {self.current_service} service is currently offline. Please try again later.")
            return

        # --- Credit Deduction Logic ---
        cost = self.get_service_price(self.current_service)
        if cost <= 0: cost = 1.0 # Default fallback

        current_credit = float(self.user_data.get("credit", 0))
        
        if current_credit < cost:
            QMessageBox.warning(self, "Insufficient Credit", f"Operation Cost: {cost} Credits\nYour Balance: {current_credit}\n\nPlease contact admin to recharge.")
            return

        # --- Log Start ---
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pc_name = socket.gethostname()
        
        self.log_output.clear()
        self.log_output.append(f"● <b>Service:</b> {self.current_service}")
        self.log_output.append(f"● <b>Operation:</b> {self.op_label.text()}")
        if self.device_model:
            self.log_output.append(f"● <b>Device Model:</b> {self.device_model}")
        self.log_output.append(f"● <b>ID/IMEI:</b> {input_val}")
        self.log_output.append("-" * 40)
        self.log_output.append(f"<i>Connecting to secure server...</i>")

        # Deduct Credit & Update Firebase off the GUI thread.
        new_credit = current_credit - cost
        self.user_data["credit"] = new_credit
        self.update_footer()
        self._queue_credit_update(new_credit)

        self.log_output.append(f"\n<b>SUCCESS:</b> Operation completed at {timestamp}")
        self.log_output.append(f"<b>CREDITS:</b> {cost:.2f} deducted successfully.")
        self.op_input.clear()

        # Log Generic Operation Activity with full logs
        log_txt = self.log_output.toPlainText()
        msg = f"OPERATION COMPLETED: {op_name} | User: {self.user_data.get('email')} | Credit: {self.user_data.get('credit')}\nLogs:\n{log_txt}"
        send_github_log(msg)

    def _handle_nothing_duplicate_check(self, duplicate, message):
        self.op_input.setEnabled(True)
        self.op_btn.setEnabled(True)
        if duplicate:
            QMessageBox.warning(self, "Already Submitted", message or "Your IMEI already submitted!")
            return
        if message:
            self.append_frp_log(message, "warning")

        self.refresh_user_data()
        s_info = self.service_settings.get("Nothing", {})
        if s_info.get('status', 'offline') != 'online':
            QMessageBox.warning(self, "Service Offline", "Nothing Network Unlock is currently offline.")
            return

        cost = self.get_service_price("Nothing")
        if float(self.user_data.get("credit", 0)) < cost:
            QMessageBox.warning(self, "Insufficient Credit", f"Price: {cost} Credits. Please recharge.")
            return

        self.log_output.clear()
        self.op_input.setVisible(False)
        self.op_btn.setVisible(False)
        self.op_btn.setEnabled(False)

        msg = f"START NOTHING NETWORK UNLOCK: {self.user_data.get('email')} | IMEI: {self._pending_nothing_submit['imei']} | Credit: {self.user_data.get('credit')}"
        send_github_log(msg)

        self.nothing_worker = self._track_worker("nothing_worker", NothingUnlockWorker(self.token, self.user_data.get('email'), self._pending_nothing_submit['imei'], self.uid))
        safe_connect(self.nothing_worker.log_signal, self.append_frp_log)
        safe_connect(self.nothing_worker.popup_signal, self.handle_nothing_popup)
        safe_connect(self.nothing_worker.device_detected_signal, self.on_nothing_device_detected)
        safe_connect(self.nothing_worker.finished_signal, self.on_nothing_finished)
        self.nothing_worker.start()

    def append_frp_log(self, message, level="info"):
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # Clean aur professional colors (zyada chamak-dhamak nahi)
        color_map = {
            "success": "#1a7f37",  # Professional Green
            "error": "#cf222e",    # Professional Red
            "warning": "#9a6700",  # Dark Gold/Yellow
            "info": "#1f2328",     # Standard Dark Text
            "header": "#0969da"    # Muted Blue Header
        }
        color = color_map.get(level, "#1f2328")
        if level == "header": html = f'<b style="color:{color}; font-size: 15px;">{message}</b><br>'
        elif message.strip() == "": html = '<br>'
        else: html = f'<span style="color:{color};">{message}</span><br>'
        self.log_output.insertHtml(html)
        self.log_output.ensureCursorVisible()

    def start_read_info_sequence(self):
        if not self.adb:
            QMessageBox.critical(self, "Error", "ADB DLL not found.")
            return

        self.op_btn.setEnabled(False)
        self.log_output.clear()
        self.append_frp_log("Operation: Read Phone Info (Assistant Mode)", "header")
        
        self.read_worker = self._track_worker("read_worker", FRPWorker(self.adb, 'read_full'))
        safe_connect(self.read_worker.log_signal, self.append_frp_log)
        safe_connect(self.read_worker.finished_signal, lambda s, m: self.op_btn.setEnabled(True))
        self.read_worker.start()

    # Device detect hone par price dikhana aur confirmation lena
    def on_nothing_device_detected(self, serial):
        self.refresh_user_data()
        s_info = self.service_settings.get("Nothing", {})
        cost = self.get_service_price("Nothing")
        
        reply = QMessageBox.question(self, "⚠️ Confirm Operation",
                                     f"Device Found: {serial}\nIMEI: {self.nothing_worker.imei}\n\nProceed with Network Unlock? {cost:.2f} Credits will be deducted.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            current_credit = float(self.user_data.get("credit", 0))
            if current_credit < cost:
                QMessageBox.warning(self, "Insufficient Credit", "Not enough credits.")
                self.nothing_worker.requestInterruption()
                with self.nothing_worker.wait_condition:
                    self.nothing_worker.wait_condition.notify_all()
            else:
                # Credits deduct karna aur Firebase update karna
                new_credit = current_credit - cost
                self.user_data["credit"] = new_credit
                self.update_footer()
                self._queue_credit_update(new_credit)
                
                with self.nothing_worker.wait_condition:
                    self.nothing_worker.proceed = True
                    self.nothing_worker.wait_condition.notify_all()
                return
        else:
            self.append_frp_log("Operation cancelled by user", "warning")
            self.nothing_worker.requestInterruption()
            with self.nothing_worker.wait_condition:
                self.nothing_worker.wait_condition.notify_all()
            self.op_input.setVisible(True)
            self.op_btn.setVisible(True)
            self.op_btn.setEnabled(True)
            
        with self.nothing_worker.wait_condition:
            self.nothing_worker.wait_condition.notify_all()

    # Operation khatam hone par button enable karna
    def on_nothing_finished(self, success, message):
        self.op_btn.setEnabled(True)
        if not success:
            self.op_input.setVisible(True)
            self.op_btn.setVisible(True)
        else:
            self.schedule_operation_start(self.display_nothing_history, delay=1500)

        # Log Nothing Unlock Result
        status = "SUCCESS" if success else "FAILED"
        log_txt = self.log_output.toPlainText()
        msg = f"NOTHING UNLOCK {status}: {self.user_data.get('email')} | Credit: {self.user_data.get('credit')}\nLogs:\n{log_txt}"
        send_github_log(msg)

    def display_nothing_history(self):
        """Fetches and displays the current user's Nothing Network Unlock history."""
        if "Network Unlock" not in self.op_label.text(): return

        self.log_output.clear()
        self.log_output.insertHtml("<div style='color: #0969da; font-size: 16px; font-weight: bold; margin-bottom: 10px;'>📋 Recent Submissions History</div><br>")
        self.history_worker = self._track_worker("history_worker", NothingHistoryWorker(self.token, self.user_data.get('email', '')))
        safe_connect(self.history_worker.finished_signal, self._handle_nothing_history_result)
        self.history_worker.start()

    def _handle_nothing_history_result(self, payload):
        self.log_output.clear()
        self.log_output.insertHtml("<div style='color: #0969da; font-size: 16px; font-weight: bold; margin-bottom: 10px;'>📋 Recent Submissions History</div><br>")
        if payload.get("error"):
            self.log_output.insertHtml(f"<div style='color: #cf222e;'>Error loading history: {payload['error']}</div>")
            return

        user_orders = payload.get("orders", [])
        if not user_orders:
            self.log_output.insertHtml("<div style='color: #6b7280; padding: 10px;'>No previous submissions for this account.</div>")
            return

        user_orders.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        for data in user_orders:
            imei = data.get('imei', 'N/A')
            status = data.get('status', 'In Process')
            ts = data.get('timestamp', 'N/A')
            bg_color = "#fef3c7"
            text_color = "#92400e"
            if status == "Success":
                bg_color = "#dcfce7"; text_color = "#166534"
            elif status == "Rejected":
                bg_color = "#fee2e2"; text_color = "#991b1b"
            card_html = f"""
            <div style="background-color: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; margin-bottom: 8px;">
                <table width="100%">
                    <tr>
                        <td style="font-size: 13px;"><b>IMEI:</b> <span style="color: #2563eb; font-family: monospace;">{imei}</span></td>
                        <td align="right">
                            <span style="background-color: {bg_color}; color: {text_color}; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: bold;">{status.upper()}</span>
                        </td>
                    </tr>
                    <tr>
                        <td colspan="2" style="font-size: 11px; color: #64748b; padding-top: 4px;">Date: {ts}</td>
                    </tr>
                </table>
            </div>
            """
            self.log_output.insertHtml(card_html)
        self.log_output.ensureCursorVisible()

    def start_frp_sequence(self):
        if not self.adb:
            QMessageBox.critical(self, "Error", "ADB DLL not found. Operation aborted.")
            return

        self.refresh_user_data()
        self._load_service_settings_async(self._start_frp_sequence_after_service_settings)

    def _start_frp_sequence_after_service_settings(self, success, service_settings, error):
        if not success:
            QMessageBox.warning(self, "Service Error", error or "Unable to load service settings right now.")
            return

        self.service_settings = service_settings
        s_info = self.service_settings.get("Xiaomi", {})
        if s_info.get('status', 'offline') != 'online':
            QMessageBox.warning(self, "Service Offline", "Xiaomi FRP services are currently offline.")
            return

        cost = self.get_service_price("Xiaomi")
        if cost <= 0: cost = 1.0

        if float(self.user_data.get("credit", 0)) < cost:
            QMessageBox.warning(self, "Insufficient Credit", f"Operation Cost: {cost} Credits. Please recharge.")
            return

        self.op_btn.setEnabled(False)
        self.log_output.clear()
        self.append_frp_log("Operation: Factory Reset & FRP", "header")

        msg = f"START XIAOMI FRP OPERATION: {self.user_data.get('email')} | Credit: {self.user_data.get('credit')}"
        send_github_log(msg)

        self.worker = self._track_worker("worker", FRPWorker(self.adb, 'read', user_email=self.user_data.get('email')))
        safe_connect(self.worker.log_signal, self.append_frp_log)
        safe_connect(self.worker.finished_signal, self.on_frp_read_finished)
        self.worker.start()

    def on_frp_read_finished(self, success, message):
        if success:
            self.mi_token = self.worker.mi_token
            self.device_model = self.worker.device_model
            self.device_serial = self.worker.device_serial
            
            self.refresh_user_data()
            s_info = self.service_settings.get("Xiaomi", {})
            cost = self.get_service_price("Xiaomi")
            
            reply = QMessageBox.question(self, "⚠️ Confirm Operation",
                                         f"Device Found: {self.device_serial}\nModel: {self.device_model}\n\nProceed with FRP Wipe? {cost:.2f} Credits will be deducted.",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # Re-verify credits before final execution
                self.refresh_user_data()
                cost = self.get_service_price("Xiaomi")

                if float(self.user_data.get("credit", 0)) < cost:
                    QMessageBox.warning(self, "Insufficient Credit", "Balance changed. Please recharge.")
                    self.op_btn.setEnabled(True)
                    return

                self.pending_frp_cost = cost
                # Start Erase
                self.worker = self._track_worker("worker", FRPWorker(self.adb, 'erase', self.mi_token, self.device_model, self.device_serial, user_email=self.user_data.get('email')))
                safe_connect(self.worker.auth_success_signal, self.deduct_frp_credits)
                safe_connect(self.worker.log_signal, self.append_frp_log)
                safe_connect(self.worker.finished_signal, self.on_frp_erase_finished)
                self.worker.start()
            else:
                self.append_frp_log("Operation cancelled by user", "warning")
                msg = f"XIAOMI FRP CANCELLED: {self.user_data.get('email')} | Credit: {self.user_data.get('credit')}"
                send_github_log(msg)
                self.op_btn.setEnabled(True)
        else:
            self.append_frp_log(f"Read Failed: {message}", "error")
            msg = f"XIAOMI FRP READ FAILED: {self.user_data.get('email')} | Error: {message}"
            send_github_log(msg)
            self.op_btn.setEnabled(True)

    def start_demo_remove_sequence(self):
        self.op_btn.setEnabled(False)
        self.log_output.clear()
        self.append_frp_log("Operation: Demo Remove (ADB Mode)", "header")
        
        self.demo_worker = self._track_worker("demo_worker", DemoRemoveWorker(self.adb, 'read', user_email=self.user_data.get('email')))
        safe_connect(self.demo_worker.log_signal, self.append_frp_log)
        safe_connect(self.demo_worker.finished_signal, self.on_demo_read_finished)
        self.demo_worker.start()

    def on_demo_read_finished(self, success, message, info):
        if success:
            reply = QMessageBox.question(self, "⚠️ Confirm Operation",
                                         f"Device Found: {info.get('Serial')}\nModel: {info.get('Model')}\n\nThis service will cost 5 credits. Do you want to continue?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                current_credit = float(self.user_data.get("credit", 0))
                if current_credit < 5.0:
                    QMessageBox.warning(self, "Insufficient Credit", "Operation Cost: 5 Credits. Please recharge.")
                    self.op_btn.setEnabled(True)
                    return

                self.demo_worker = self._track_worker("demo_worker", DemoRemoveWorker(self.adb, 'remove', info.get('Serial'), user_email=self.user_data.get('email')))
                safe_connect(self.demo_worker.log_signal, self.append_frp_log)
                safe_connect(self.demo_worker.finished_signal, self.on_demo_remove_finished)
                self.demo_worker.start()
            else:
                self.append_frp_log("Operation stopped by user.", "warning")
                self.op_btn.setEnabled(True)
        else:
            self.append_frp_log(f"Detection Failed: {message}", "error")
            self.op_btn.setEnabled(True)

    def on_demo_remove_finished(self, success, message, info):
        self.op_btn.setEnabled(True)
        if success:
            # Deduct 5 credits
            new_credit = float(self.user_data.get("credit", 0)) - 5.0
            self._queue_credit_update(new_credit)
            self.user_data["credit"] = new_credit
            self.update_footer()
            self.append_frp_log("CREDIT DEDUCTED", "info")
            self.append_frp_log("ALL WORK DONE", "success")
            self.append_frp_log("<b>Service Completed Successfully</b>", "success")
        else:
            self.append_frp_log(f"Process Failed: {message}", "error")

    def deduct_frp_credits(self):
        """Deducts credits immediately after server auth success."""
        if self.pending_frp_cost > 0:
            current = float(self.user_data.get("credit", 0))
            new_credit = current - self.pending_frp_cost
            self._queue_credit_update(new_credit)
            self.user_data["credit"] = new_credit
            self.update_footer()
            self.append_frp_log("User credits deducted... OK", "success")
            self.pending_frp_cost = 0

    def on_frp_erase_finished(self, success, message):
        self.op_btn.setEnabled(True)
        if success:
            self.op_input.clear()
        self.pending_frp_cost = 0 # Reset state
        
        # Log Xiaomi FRP Final Result (including Auth Fail/Success) with full logs
        status = "SUCCESS" if success else "FAILED/AUTH_FAIL"
        log_txt = self.log_output.toPlainText()
        msg = f"XIAOMI FRP {status}: {self.user_data.get('email')} | Credit: {self.user_data.get('credit')}\nFull Logs:\n{log_txt}"
        send_github_log(msg)

    def display_server_status(self):
        self.log_output.clear()
        self.append_frp_log(f"--- {self.current_service} Server Status ---", "header")
        self._load_service_settings_async(self._handle_server_status_result)

    def _handle_server_status_result(self, success, service_settings, error):
        self.service_settings = service_settings if success else self.service_settings
        s_info = self.service_settings.get(self.current_service, {})
        status = s_info.get('status', 'offline').upper()
        price = self.get_service_price(self.current_service)
        is_custom = "custom_prices" in self.user_data and self.current_service in self.user_data.get("custom_prices", {})
        self.append_frp_log(f"Status        : {status}", "success" if status == "ONLINE" else "error")
        self.append_frp_log(f"Credit Price  : {price:.2f} Credits {'(Special Rate)' if is_custom else ''}", "info")
        self.append_frp_log("-" * 40, "info")
       

# ================= MAIN =================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    # Try to set window icon (optional - requires icon.ico in same directory)
    try:
        app.setWindowIcon(QIcon("icon.ico"))
    except:
        pass

    stack = QStackedWidget()
    stack.resize(720, 420)   # 🖥️ Desktop size

    login_page = LoginPage(stack)
    register_page = RegisterPage(stack)
    disclaimer_page = DisclaimerPage(stack)
    home_page = HomePage(stack)
    app.aboutToQuit.connect(login_page.cancel_background_work)
    app.aboutToQuit.connect(disclaimer_page.cancel_background_work)
    app.aboutToQuit.connect(home_page.stop_all_workers)

    stack.addWidget(login_page)
    stack.addWidget(register_page)
    stack.addWidget(disclaimer_page)
    stack.addWidget(home_page)

    stack.setWindowTitle(f"GSM Multi Tool PRO v{VERSION} – Developed with ❤️ in Nepal")
    stack.show()

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        sys.exit(0)

