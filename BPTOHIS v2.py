import os
import sys
import json
import threading
import queue
import time
from time import sleep
import sqlite3
from datetime import datetime, date

from flask import Flask, render_template, request, jsonify, Response

from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.CardType import AnyCardType
from smartcard.CardRequest import CardRequest
from smartcard.System import readers
import serial
import serial.tools.list_ports
import requests
from gtts import gTTS
import pygame
import pystray
from PIL import Image
import hashlib

# ==========================================
# G L O B A L   S T A T E
# ==========================================
# PyInstaller support: detect bundled path
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(base_path, 'templates'),
            static_folder=os.path.join(base_path, 'static'))
subscribers = []
card_inserted_flag = False
serial_connection = None
serial_thread = None
high_bp_records = {}  # {cid: timestamp} สำหรับตรวจสอบการวัดซ้ำ
HIGH_BP_REPEAT_WINDOW = 30 * 60  # 30 นาที (วินาที)

# ==========================================
# D A T A B A S E   (SQLite local log)
# ==========================================
# 5 ตำบล อำเภอโคกเจริญ
TAMBON_LIST = [
    ('โคกเจริญ',   ['โคกเจริญ']),
    ('ยางราก',     ['ยางราก']),
    ('โคกแสมสาร',  ['โคกแสมสาร', 'แสมสาร']),
    ('วังทอง',     ['วังทอง']),
    ('หนองมะค่า',  ['หนองมะค่า', 'หนองมะคา']),
]
TAMBON_OTHER = 'อื่น ๆ'

# DB path เก็บข้าง exe (ไม่ใน _MEIPASS)
if getattr(sys, 'frozen', False):
    db_path = os.path.join(os.path.dirname(sys.executable), 'bp_log.db')
else:
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bp_log.db')

def db_init():
    con = sqlite3.connect(db_path)
    con.execute('''
        CREATE TABLE IF NOT EXISTS bp_log (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT NOT NULL,
            date     TEXT NOT NULL,
            cid      TEXT,
            name     TEXT,
            tambon   TEXT,
            bps      INTEGER,
            bpd      INTEGER,
            pulse    INTEGER,
            category TEXT
        )
    ''')
    con.commit()
    con.close()

db_init()

def detect_tambon(address: str) -> str:
    """ตรวจสอบตำบลจากข้อความที่อยู่บนบัตร — match 'ตำบล X' ก่อนเสมอ"""
    if not address:
        return TAMBON_OTHER
    # รอบแรก: match "ตำบล X" หรือ "ต.X" อย่างชัดเจน (ป้องกัน อำเภอโคกเจริญ ชนกัน)
    for tambon_name, keywords in TAMBON_LIST:
        for kw in keywords:
            if f'ตำบล{kw}' in address or f'ต.{kw}' in address or f'ต {kw}' in address:
                return tambon_name
    # รอบสอง: fallback match keyword ทั่วไป (กรณีที่อยู่ไม่มีคำว่าตำบล)
    for tambon_name, keywords in TAMBON_LIST:
        for kw in keywords:
            if kw in address:
                return tambon_name
    return TAMBON_OTHER

def classify_bp(sys_v: int, dia_v: int) -> str:
    """จัดกลุ่มความดัน ตามเกณฑ์ระดับความดันโลหิต"""
    if sys_v >= 180 or dia_v >= 110:
        return 'สูงมาก'          # โรคความดันโลหิตสูง ระดับ 3
    elif sys_v >= 160 or dia_v >= 100:
        return 'สูง'             # โรคความดันโลหิตสูง ระดับ 2
    elif sys_v >= 140 and dia_v >= 90:
        return 'สูงเล็กน้อย'    # โรคความดันโลหิตสูง ระดับ 1
    elif sys_v >= 140 and dia_v < 90:
        return 'สูงเฉพาะตัวบน'  # โรคความดันโลหิตสูงเฉพาะตัวบน
    elif sys_v < 140 and dia_v >= 90:
        return 'สูงเฉพาะตัวล่าง' # โรคความดันโลหิตสูงเฉพาะตัวล่าง
    elif sys_v >= 130 or dia_v >= 85:
        return 'เสี่ยง'          # สูงกว่าปกติ
    elif sys_v >= 120 or dia_v >= 80:
        return 'ปกติ'            # ปกติ (120-129 / 80-84)
    elif sys_v < 90 or dia_v < 60:
        return 'ต่ำ'
    else:
        return 'เหมาะสม'         # เหมาะสม (<120 และ <80)

def log_measurement(patient_info: dict, sys_v: int, dia_v: int, pulse_v: int):
    """บันทึกผลวัดความดันลง SQLite"""
    try:
        now = datetime.now()
        tambon  = detect_tambon(patient_info.get('address', ''))
        category = classify_bp(sys_v, dia_v)
        con = sqlite3.connect(db_path)
        con.execute(
            'INSERT INTO bp_log (ts, date, cid, name, tambon, bps, bpd, pulse, category) VALUES (?,?,?,?,?,?,?,?,?)',
            (now.isoformat(), now.strftime('%Y-%m-%d'),
             patient_info.get('cid', ''), patient_info.get('name', ''),
             tambon, sys_v, dia_v, pulse_v, category)
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f'DB log error: {e}')

# ==========================================
# U T I L S
# ==========================================
def load_config():
    web_app_url = ""
    com_port    = "Auto"
    github_repo = ""
    try:
        with open("config.txt", "r") as file:
            lines = file.readlines()
            if len(lines) >= 1: web_app_url = lines[0].strip()
            if len(lines) >= 2: com_port    = lines[1].strip()
            if len(lines) >= 3: github_repo = lines[2].strip()
    except FileNotFoundError:
        pass
    return web_app_url, com_port, github_repo

def save_config(web_app_url, com_port, github_repo=""):
    with open("config.txt", "w") as file:
        file.write(web_app_url  + "\n")
        file.write(com_port     + "\n")
        file.write(github_repo  + "\n")

def publish_event(event_type, message="", data=None):
    payload = {"type": event_type, "message": message, "data": data or {}}
    for q in subscribers:
        q.put(payload)

def play_audio(text):
    try:
        audio_dir = os.path.join(base_path, 'static', 'audio')
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)
            
        filename = hashlib.md5(text.encode('utf-8')).hexdigest() + ".mp3"
        filepath = os.path.join(audio_dir, filename)

        if not os.path.exists(filepath):
            try:
                tts = gTTS(text, lang='th')
                tts.save(filepath)
            except Exception as e:
                print(f"Internet/TTS error: {e}")
                publish_event('log', "ไม่สามารถสร้างเสียงใหม่ได้ กรุณาเชื่อมต่ออินเทอร์เน็ตในครั้งแรก")
                return

        pygame.mixer.init()
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    except Exception as e:
        print(f"Audio error: {e}")

def send_to_google_sheet(data, url):
    try:
        response = requests.post(url, json=data, allow_redirects=True, timeout=15)
        if response.status_code == 200 or response.status_code == 201:
            try:
                res_json = response.json()
                return res_json.get("status") == "success" or res_json.get("success") == True
            except:
                return True
        return response.ok
    except Exception as e:
        print(f"Error sending data to Google Sheet: {e}")
        return False

# ==========================================
# A U T O   U P D A T E R
# ==========================================
def _get_app_dir() -> str:
    """Path โฟลเดอร์ที่เก็บ exe (ไม่ใช่ _MEIPASS)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _get_current_version() -> str:
    try:
        vpath = os.path.join(_get_app_dir(), 'version.txt')
        with open(vpath, 'r') as f:
            return f.read().strip()
    except:
        return "0.0.0"

def _parse_version(v: str):
    try:
        return tuple(int(x) for x in v.lstrip('v').split('.'))
    except:
        return (0, 0, 0)

def check_for_update():
    """Background thread: เช็คเวอร์ชันใหม่จาก GitHub Releases"""
    _, _, github_repo = load_config()
    if not github_repo or '/' not in github_repo:
        return  # ยังไม่ได้ตั้งค่า repo
    try:
        current = _get_current_version()
        api_url = f"https://api.github.com/repos/{github_repo}/releases/latest"
        resp = requests.get(api_url, timeout=10,
                            headers={'Accept': 'application/vnd.github.v3+json'})
        if resp.status_code != 200:
            return
        release  = resp.json()
        latest   = release.get('tag_name', '').lstrip('v')
        if _parse_version(latest) <= _parse_version(current):
            publish_event('log', f"เวอร์ชัน {current} เป็นล่าสุดแล้ว")
            return
        # มีเวอร์ชันใหม่
        notes = release.get('body', '') or ''
        publish_event('update_available', f"พบเวอร์ชันใหม่ v{latest}",
                      {"current": current, "latest": latest, "notes": notes})
        # หา asset .zip
        asset_url = next(
            (a['browser_download_url']
             for a in release.get('assets', [])
             if a['name'].lower().endswith('.zip')),
            None
        )
        if not asset_url:
            publish_event('log', 'ไม่พบไฟล์ .zip ใน GitHub Release')
            return
        _download_and_prepare(asset_url, latest)
    except Exception as e:
        print(f"Update check error: {e}")

def _download_and_prepare(url: str, new_version: str):
    """Download ZIP และเตรียม _updater.bat"""
    import tempfile, zipfile, shutil
    tmp      = tempfile.gettempdir()
    zip_path = os.path.join(tmp, '_bptohis_update.zip')
    new_dir  = os.path.join(tmp, '_bptohis_new')
    app_dir  = _get_app_dir()

    try:
        # ---- Download ----
        publish_event('update_progress', 'กำลังดาวน์โหลด...', {'percent': 0})
        resp  = requests.get(url, stream=True, timeout=120)
        total = int(resp.headers.get('content-length', 0))
        done  = 0
        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
                done += len(chunk)
                pct = int(done / total * 80) if total else 0
                publish_event('update_progress', f'ดาวน์โหลด {pct}%', {'percent': pct})

        # ---- Extract ----
        publish_event('update_progress', 'กำลังแตกไฟล์...', {'percent': 85})
        shutil.rmtree(new_dir, ignore_errors=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(new_dir)
        os.remove(zip_path)

        # หา subfolder ใน ZIP
        subs = [d for d in os.listdir(new_dir)
                if os.path.isdir(os.path.join(new_dir, d))]
        src  = os.path.join(new_dir, subs[0]) if subs else new_dir

        # ---- Create _updater.bat ----
        exe_path = sys.executable if getattr(sys, 'frozen', False) else ""
        bat_path = os.path.join(app_dir, '_updater.bat')
        bat = (
            f'@echo off\n'
            f'chcp 65001 >nul\n'
            f'timeout /t 3 /nobreak >nul\n'
            f'robocopy "{src}" "{app_dir}" /E /IS /IT /NFL /NDL /NJH /NJS\n'
            f'echo {new_version}> "{os.path.join(app_dir, "version.txt")}"\n'
            f'rmdir /s /q "{new_dir}"\n'
        )
        if exe_path:
            bat += f'start "" "{exe_path}"\n'
        bat += 'del "%~f0"\n'

        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat)

        publish_event('update_progress', 'เสร็จแล้ว', {'percent': 100})
        publish_event('update_ready', f'พร้อมอัปเดตเป็น v{new_version}',
                      {'new_version': new_version, 'bat_path': bat_path})

        # อัเปดตอัตโนมัติหลัง 10 วินาที (ให้เวลาให้เจ้าหน้าที่เห็นก่อน)
        threading.Timer(10.0, _apply_update_now, args=[bat_path]).start()
    except Exception as e:
        publish_event('log', f'เกิดข้อผิดพลาดในการดาวน์โหลด: {e}')
        print(f'Update download error: {e}')

def _apply_update_now(bat_path: str):
    """รัน updater batch แล้วปิดโปรแกรมอัตโนมัติ"""
    import subprocess
    if not os.path.exists(bat_path):
        return
    subprocess.Popen(['cmd', '/c', bat_path],
                     creationflags=subprocess.CREATE_NO_WINDOW,
                     close_fds=True)
    time.sleep(1)
    os._exit(0)

def update_check_loop():
    """เช็คอัปเดตทุก 1 ชั่วโมง"""
    while True:
        try:
            check_for_update()
        except Exception as e:
            print(f'Update loop error: {e}')
        time.sleep(3600)  # 1 ชั่วโมง



def auto_find_com_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        return port.device
    return 'COM3'

# ==========================================
# B L O O D   P R E S S U R E   R E A D E R
# ==========================================
def is_repeat_high(cid):
    """ตรวจสอบว่า CID นี้เคยวัดได้สูงภายใน HIGH_BP_REPEAT_WINDOW วินาทีที่ผ่านมาหรือไม่"""
    if cid in high_bp_records:
        elapsed = time.time() - high_bp_records[cid]
        if elapsed <= HIGH_BP_REPEAT_WINDOW:
            return True
    return False

def record_high_bp(cid):
    """บันทึก timestamp ที่วัดได้สูงสำหรับ CID นี้"""
    high_bp_records[cid] = time.time()

def get_bp_audio_text(sys_v: int, dia_v: int, cid: str) -> str:
    """สร้างข้อความเสียงตามระดับความดัน และบันทึก high-BP record ถ้าจำเป็น"""
    repeat = is_repeat_high(cid)

    # ระดับ 3: ≥180/≥110 — ควรรีบพบแพทย์ทันที
    if sys_v >= 180 or dia_v >= 110:
        record_high_bp(cid)
        if repeat:
            return "ท่านวัดความดันซ้ำและยังคงสูงมาก กรุณาไปพบแพทย์ทันทีค่ะ"
        return "ความดันโลหิตของท่านสูงมาก กรุณานั่งพักผ่อน 15 นาที แล้วถอดบัตรเสียบใหม่เพื่อวัดซ้ำ"

    # ระดับ 2: 160-179/100-109 — ควรรีบพบแพทย์
    if sys_v >= 160 or dia_v >= 100:
        record_high_bp(cid)
        if repeat:
            return "ท่านวัดความดันซ้ำและยังคงสูง กรุณาพบแพทย์เพื่อรับการรักษาที่เหมาะสมค่ะ"
        return "ความดันโลหิตของท่านสูง กรุณานั่งพักผ่อน 15 นาที แล้วถอดบัตรเสียบใหม่เพื่อวัดซ้ำ"

    # ระดับ 1: 140-159/90-99 — ควรพบแพทย์
    if sys_v >= 140 or dia_v >= 90:
        record_high_bp(cid)
        if repeat:
            return "ท่านวัดความดันซ้ำและยังคงสูง กรุณาพบแพทย์เพื่อรับการวินิจฉัยและเข้าสู่กระบวนการปรับเปลี่ยนพฤติกรรมค่ะ"
        return "ความดันโลหิตของท่านสูง กรุณานั่งพักผ่อน 15 นาที แล้วถอดบัตรเสียบใหม่เพื่อวัดซ้ำ"

    # สูงกว่าปกติ: 130-139/85-89 — ควรปรับเปลี่ยนพฤติกรรม
    if sys_v >= 130 or dia_v >= 85:
        return "ความดันโลหิตของท่านสูงกว่าปกติ กรุณาลดน้ำหนัก ลดเกลือ มีกิจกรรมทางกายสม่ำเสมอ และงดสูบบุหรี่ค่ะ"

    # ปกติ: 120-129/80-84
    if sys_v >= 120 or dia_v >= 80:
        return "ความดันโลหิตของท่านอยู่ในเกณฑ์ปกติ กรุณาควบคุมอาหาร มีกิจกรรมทางกาย และวัดความดันอย่างสม่ำเสมอค่ะ"

    # เหมาะสม: <120 และ <80
    if sys_v >= 90 and dia_v >= 60:
        return "ความดันโลหิตของท่านอยู่ในเกณฑ์เหมาะสม ขอให้รักษาสุขภาพที่ดีต่อไปค่ะ"

    # ต่ำ
    return "ความดันโลหิตของท่านค่อนข้างต่ำ กรุณาปรึกษาเจ้าหน้าที่ค่ะ"

def get_blood_pressure_data(patient_info):
    global serial_connection, card_inserted_flag
    port_used = ""
    try:
        web_app_url, com_port = load_config()
        if com_port == 'Auto' or not com_port:
            port_used = auto_find_com_port()
        else:
            port_used = com_port

        baudrate = 9600
        serial_connection = serial.Serial(port_used, baudrate)
        publish_event('log', f"รอรับข้อมูลความดันจากพอร์ต {port_used}...")
        
        while card_inserted_flag:
            if serial_connection.in_waiting:
                blood_pressure = serial_connection.readline()
                try:
                    blood_pressure = blood_pressure.decode('utf-8')
                except UnicodeDecodeError:
                    continue

                values = blood_pressure.strip().split(',')
                if len(values) == 11:
                    year, month, day, hour, minute, _, _, systolic, diastolic, pulse, _ = values
                    publish_event('log', f"ได้รับข้อมูลความดันแล้ว {systolic}/{diastolic}")
                    
                    bp_data = {
                        "bps": systolic,
                        "bpd": diastolic,
                        "pulse": pulse
                    }
                    publish_event('bp_result', "ได้รับผลความดัน", bp_data)
                    
                    # Play Audio
                    try:
                        sys_v = int(systolic.strip())
                        dia_v = int(diastolic.strip())
                        pulse_v = int(pulse.strip())
                    except ValueError as e:
                        publish_event('log', f"ข้อมูลความดันไม่ถูกต้อง: SYS={systolic!r} DIA={diastolic!r} Pulse={pulse!r}")
                        break
                    
                    cid = patient_info.get("cid", "")
                    text = get_bp_audio_text(sys_v, dia_v, cid)
                    play_audio(text)
                    
                    # บันทึก local DB ก่อนเสมอ
                    log_measurement(patient_info, sys_v, dia_v, pulse_v)
                    publish_event('daily_summary_update', "อัปเดตสรุปประจำวัน")

                    # Send to Google Sheets
                    if web_app_url:
                        publish_event('log', "กำลังส่งข้อมูลเข้า Google Sheets...")
                        sheet_data = {
                            "cid": patient_info.get("cid", ""),
                            "name": patient_info.get("name", ""),
                            "address": patient_info.get("address", ""),
                            "bps": systolic,
                            "bpd": diastolic,
                            "pulse": pulse
                        }
                        success = send_to_google_sheet(sheet_data, web_app_url)
                        publish_event('sheet_status', "ส่งข้อมูล", {"success": success})
                    else:
                        publish_event('log', "ไม่พบ Web App URL ไม่สามารถบันทึกได้")
                        publish_event('sheet_status', "ไม่ได้ตั้งค่า URL", {"success": False})
                    
                    break # Stop reading after first success
                else:
                    publish_event('log', "ข้อมูลที่ได้รับจากเครื่องวัดความดันไม่ถูกต้อง")
            else:
                sleep(0.5)

    except serial.SerialException as e:
        publish_event('log', f"เกิดข้อผิดพลาดในการเชื่อมต่อพอร์ต {port_used}: {e}")
    finally:
        if serial_connection:
            serial_connection.close()
            serial_connection = None

# ==========================================
# S M A R T C A R D   S E T U P
# ==========================================
class PrintObserver(CardObserver):
    def update(self, observable, actions):
        global card_inserted_flag, serial_thread
        (addedcards, removedcards) = actions
        
        for _ in addedcards:
            patient_info = None
            for overall_attempt in range(3):
                try:
                    if overall_attempt > 0:
                        publish_event('log', f"กำลังลองอ่านบัตรใหม่ครั้งที่ {overall_attempt+1}...")
                        sleep(1)
                    else:
                        sleep(1.5) # Wait for contacts to stabilize
                    
                    cardtype = AnyCardType()
                    cardrequest = CardRequest(timeout=1, cardType=cardtype)
                    cardservice = cardrequest.waitforcard()
                    cardservice.connection.connect()

                    SELECT = [0x00, 0xA4, 0x04, 0x00, 0x08]
                    THAI_ID_CARD = [0xA0, 0x00, 0x00, 0x00, 0x54, 0x48, 0x00, 0x01]
                    CMD_CID = [0x80, 0xb0, 0x00, 0x04, 0x02, 0x00, 0x0d]
                    CMD_THAINAME = [0x80, 0xb0, 0x00, 0x11, 0x02, 0x00, 0x64]
                    CMD_ADDRESS = [0x80, 0xb0, 0x15, 0x79, 0x02, 0x00, 0xA0]

                    def get_data(cmd):
                        current_cmd = list(cmd)
                        response, sw1, sw2 = cardservice.connection.transmit(current_cmd)
                        if sw1 == 0x6C:
                            current_cmd[-1] = sw2
                            response, sw1, sw2 = cardservice.connection.transmit(current_cmd)
                        if sw1 == 0x61:
                            GET_RESPONSE = [0X00, 0xC0, 0x00, 0x00]
                            apdu = GET_RESPONSE + [sw2]
                            response, sw1, sw2 = cardservice.connection.transmit(apdu)
                        return response if response else []

                    response, sw1, sw2 = cardservice.connection.transmit(SELECT + THAI_ID_CARD)
                    if sw1 not in (0x61, 0x90):
                        raise Exception("Failed to Select Thai ID Applet")

                    # ID CARD
                    res_cid = get_data(CMD_CID)
                    cid = ''.join(chr(i) for i in res_cid).strip()
                    if not cid: raise Exception("Could not read CID")

                    # THAI NAME
                    res_name = get_data(CMD_THAINAME)
                    thai_name_raw = bytes(res_name).decode('tis-620', errors='ignore').strip()
                    name = ' '.join(thai_name_raw.replace('#', ' ').split())

                    # ADDRESS
                    res_addr = get_data(CMD_ADDRESS)
                    address = bytes(res_addr).decode('tis-620', errors='ignore').strip().replace('#', ' ')

                    patient_info = {
                        "cid": cid,
                        "name": name,
                        "address": address
                    }
                    
                    break # Success

                except Exception as e:
                    publish_event('log', f"อ่านบัตรไม่สำเร็จ (รอบ {overall_attempt+1}): {e}")
                    try:
                        cardservice.connection.disconnect()
                    except:
                        pass
                    
            if patient_info:
                card_inserted_flag = True
                publish_event('card_inserted', "อ่านข้อมูลสำเร็จ", patient_info)
                
                # We start a new thread to play audio and read blood pressure
                def work_thread():
                    play_audio("กรุณาวัดความดันโลหิต")
                    get_blood_pressure_data(patient_info)
                
                serial_thread = threading.Thread(target=work_thread)
                serial_thread.daemon = True
                serial_thread.start()
            else:
                publish_event('log', "ไม่สามารถอ่านบัตรได้ กรุณาถอดและเสียบใหม่")
                
        for _ in removedcards:
            card_inserted_flag = False
            publish_event('card_removed', "บัตรถูกถอดออก")
            if serial_connection:
                try:
                    serial_connection.close()
                except:
                    pass

# ==========================================
# F L A S K   R O U T E S
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    available_readers = readers()
    return jsonify({
        "readers": [str(r) for r in available_readers],
        "card_inserted": card_inserted_flag
    })

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'POST':
        data = request.json
        save_config(data.get('web_app_url', ''),
                    data.get('com_port', 'Auto'),
                    data.get('github_repo', ''))
        return jsonify({"success": True})
    else:
        url, port, repo = load_config()
        return jsonify({
            "web_app_url":  url,
            "com_port":     port,
            "github_repo":  repo,
            "version":      _get_current_version(),
        })

@app.route('/api/ports')
def api_ports():
    ports = [port.device for port in serial.tools.list_ports.comports()]
    return jsonify(ports)

@app.route('/api/test_submit', methods=['POST'])
def api_test_submit():
    data = request.json
    url = data.get('url', '')
    test_data = {
        "cid": "1234567890123",
        "name": "TEST SYSTEM",
        "address": "123 เทส",
        "bps": "120",
        "bpd": "80",
        "pulse": "75"
    }
    success = send_to_google_sheet(test_data, url)
    return jsonify({"success": success})

@app.route('/api/check_update', methods=['POST'])
def api_check_update():
    """Manual trigger ตรวจสอบอัปเดต"""
    threading.Thread(target=check_for_update, daemon=True).start()
    return jsonify({"success": True, "message": "กำลังตรวจสอบ..."})

@app.route('/api/apply_update', methods=['POST'])
def api_apply_update():
    """รัน _updater.bat แล้วปิดโปรแกรม"""
    bat_path = os.path.join(_get_app_dir(), '_updater.bat')
    if not os.path.exists(bat_path):
        return jsonify({"success": False, "message": "ไม่พบไฟล์ updater"})
    import subprocess
    subprocess.Popen(['cmd', '/c', bat_path],
                     creationflags=subprocess.CREATE_NO_WINDOW,
                     close_fds=True)
    threading.Timer(1.0, lambda: os._exit(0)).start()
    return jsonify({"success": True})

@app.route('/api/test_bp', methods=['POST'])
def api_test_bp():
    """ทดสอบการแสดงผลความดันและเสียงอ่าน"""
    data = request.json or {}
    sys_v = int(data.get('sys', 150))
    dia_v = int(data.get('dia', 95))
    pulse_v = int(data.get('pulse', 80))
    cid_val = data.get('cid', '1234567890123')
    
    # Send card event first (fake patient)
    publish_event('card_inserted', "อ่านข้อมูลสำเร็จ", {
        "cid": cid_val,
        "name": "ทดสอบ ระบบ",
        "address": "ที่อยู่ทดสอบ"
    })
    
    # Send BP result to frontend
    bp_data = {"bps": str(sys_v), "bpd": str(dia_v), "pulse": str(pulse_v)}
    publish_event('bp_result', "ได้รับผลความดัน", bp_data)
    
    # Play audio in background thread
    def play_test_audio():
        text = get_bp_audio_text(sys_v, dia_v, cid_val)
        play_audio(text)

    threading.Thread(target=play_test_audio, daemon=True).start()

    # บันทึก test ลง local DB ด้วย (เพื่อให้กราฟสรุปแสดงผล)
    test_patient = {"cid": cid_val, "name": "ทดสอบ ระบบ", "address": data.get('address', '')}
    log_measurement(test_patient, sys_v, dia_v, pulse_v)
    publish_event('daily_summary_update', "อัปเดตสรุปประจำวัน")

    return jsonify({"success": True, "sys": sys_v, "dia": dia_v, "pulse": pulse_v})

@app.route('/api/daily_summary')
def api_daily_summary():
    """สรุปการวัดความดันประจำวัน แยกตาม 5 ตำบล"""
    today = date.today().strftime('%Y-%m-%d')
    tambons_order = ['โคกเจริญ', 'ยางราก', 'โคกแสมสาร', 'วังทอง', 'หนองมะค่า', 'อื่น ๆ']

    try:
        con = sqlite3.connect(db_path)
        rows = con.execute(
            'SELECT tambon, category, COUNT(*) as cnt FROM bp_log WHERE date=? GROUP BY tambon, category',
            (today,)
        ).fetchall()
        total_row = con.execute(
            'SELECT COUNT(*) FROM bp_log WHERE date=?', (today,)
        ).fetchone()
        con.close()

        # สร้าง dict {tambon: {category: count}}
        data_map = {}
        for tambon, cat, cnt in rows:
            if tambon not in data_map:
                data_map[tambon] = {}
            data_map[tambon][cat] = cnt

        # จัดรูปให้ frontend ใช้ง่าย
        result = []
        for t in tambons_order:
            cats = data_map.get(t, {})
            total_t = sum(cats.values())
            if total_t == 0 and t == 'อื่น ๆ':
                continue  # ซ่อน "อื่นๆ" ถ้าไม่มีข้อมูล
            result.append({
                "tambon": t,
                "total": total_t,
                "optimal":  cats.get('เหมาะสม', 0),          # <120 และ <80
                "normal":   cats.get('ปกติ', 0),              # 120-129 / 80-84
                "risk":     cats.get('เสี่ยง', 0),            # 130-139 / 85-89 สูงกว่าปกติ
                "elevated": cats.get('สูงเล็กน้อย', 0),      # 140-159/90-99 ระดับ 1
                "sys_only": cats.get('สูงเฉพาะตัวบน', 0),    # ≥140 ตัวบนอย่างเดียว
                "dia_only": cats.get('สูงเฉพาะตัวล่าง', 0),  # ≥90 ตัวล่างอย่างเดียว
                "high":     cats.get('สูง', 0),               # 160-179/100-109 ระดับ 2
                "crisis":   cats.get('สูงมาก', 0),            # ≥180/≥110 ระดับ 3
                "low":      cats.get('ต่ำ', 0),
            })

        return jsonify({
            "date": today,
            "total": total_row[0] if total_row else 0,
            "tambons": result
        })
    except Exception as e:
        return jsonify({"error": str(e), "total": 0, "tambons": []}), 500

@app.route('/api/events')
def api_events():
    def stream():
        q = queue.Queue()
        subscribers.append(q)
        try:
            while True:
                msg = q.get()
                yield f"data: {json.dumps(msg)}\n\n"
        except GeneratorExit:
            pass
        finally:
            subscribers.remove(q)
            
    return Response(stream(), mimetype="text/event-stream")

# ==========================================
# M A I N
# ==========================================
def start_flask():
    app.run(host='127.0.0.1', port=5044, debug=False, use_reloader=False)

if __name__ == '__main__':
    import webbrowser

    # Start flask in background
    t = threading.Thread(target=start_flask)
    t.daemon = True
    t.start()

    # Give flask a moment to start
    time.sleep(1)

    # เช็คอัปเดตด้วย loop ทุก 1 ชั่วโมง (background, ไม่บล็อก startup)
    threading.Thread(target=update_check_loop, daemon=True).start()

    # Start card monitor
    cardmonitor = CardMonitor()
    cardobserver = PrintObserver()
    cardmonitor.addObserver(cardobserver)

    # System Tray Setup
    try:
        tray_image = Image.open(os.path.join(base_path, 'static', 'Logo.png'))
        tray_image = tray_image.resize((256, 256), Image.Resampling.LANCZOS)
    except Exception:
        tray_image = Image.new('RGB', (64, 64), color=(79, 70, 229))

    def on_open_browser(icon, item):
        webbrowser.open('http://127.0.0.1:5044/')

    def on_quit(icon, item):
        icon.stop()
        cardmonitor.deleteObserver(cardobserver)
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem('เปิดหน้าเว็บ', on_open_browser, default=True),
        pystray.MenuItem('ออก', on_quit)
    )

    icon = pystray.Icon("BP_System_Tray", tray_image, "BP TO GOOGLE SHEETS", menu)
    
    print("โปรแกรมทำงานในถาดระบบ (System Tray)")
    print("ดับเบิลคลิกที่ไอคอนเพื่อเปิดหน้าเว็บ")
    print(f"หรือเปิด browser ไปที่ http://127.0.0.1:5044/")
    
    # Run tray icon (this blocks until icon.stop() is called)
    icon.run()