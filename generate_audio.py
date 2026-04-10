"""
generate_audio.py
Pre-generate ไฟล์เสียงทั้งหมดที่ใช้ใน BPTOHIS v2.py
รันสคริปต์นี้ 1 ครั้ง (ต้องมีอินเทอร์เน็ต) เพื่อให้โปรแกรมทำงานออฟไลน์ได้สมบูรณ์
"""
import os
import sys
import hashlib
from gtts import gTTS

# รองรับ Windows terminal ที่ใช้ encoding ไม่ใช่ UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

base_path = os.path.dirname(os.path.abspath(__file__))
audio_dir = os.path.join(base_path, 'static', 'audio')
os.makedirs(audio_dir, exist_ok=True)

# ข้อความเสียงทั้งหมดที่ใช้ใน get_bp_audio_text() และ work_thread()
phrases = [
    # ---- เสียงเริ่มต้น ----
    "กรุณาวัดความดันโลหิต",

    # ---- ระดับ 3: ≥180/≥110 ----
    "ท่านวัดความดันซ้ำและยังคงสูงมาก กรุณาไปพบแพทย์ทันทีค่ะ",
    "ความดันโลหิตของท่านสูงมาก กรุณานั่งพักผ่อน 15 นาที แล้วถอดบัตรเสียบใหม่เพื่อวัดซ้ำ",

    # ---- ระดับ 2: 160-179/100-109 ----
    "ท่านวัดความดันซ้ำและยังคงสูง กรุณาพบแพทย์เพื่อรับการรักษาที่เหมาะสมค่ะ",
    "ความดันโลหิตของท่านสูง กรุณานั่งพักผ่อน 15 นาที แล้วถอดบัตรเสียบใหม่เพื่อวัดซ้ำ",

    # ---- ระดับ 1: 140-159/90-99 ----
    "ท่านวัดความดันซ้ำและยังคงสูง กรุณาพบแพทย์เพื่อรับการวินิจฉัยและเข้าสู่กระบวนการปรับเปลี่ยนพฤติกรรมค่ะ",
    # (ข้อความ first-time ระดับ 1 ใช้ร่วมกับระดับ 2 ข้างบนแล้ว)

    # ---- สูงกว่าปกติ: 130-139/85-89 ----
    "ความดันโลหิตของท่านสูงกว่าปกติ กรุณาลดน้ำหนัก ลดเกลือ มีกิจกรรมทางกายสม่ำเสมอ และงดสูบบุหรี่ค่ะ",

    # ---- ปกติ: 120-129/80-84 ----
    "ความดันโลหิตของท่านอยู่ในเกณฑ์ปกติ กรุณาควบคุมอาหาร มีกิจกรรมทางกาย และวัดความดันอย่างสม่ำเสมอค่ะ",

    # ---- เหมาะสม: <120 และ <80 ----
    "ความดันโลหิตของท่านอยู่ในเกณฑ์เหมาะสม ขอให้รักษาสุขภาพที่ดีต่อไปค่ะ",

    # ---- ต่ำ ----
    "ความดันโลหิตของท่านค่อนข้างต่ำ กรุณาปรึกษาเจ้าหน้าที่ค่ะ",
]

print(f"กำลังตรวจสอบ {len(phrases)} ประโยค...")
print(f"บันทึกไฟล์เสียงที่: {audio_dir}\n")

generated = 0
skipped   = 0

for text in phrases:
    filename = hashlib.md5(text.encode('utf-8')).hexdigest() + ".mp3"
    filepath = os.path.join(audio_dir, filename)
    if not os.path.exists(filepath):
        print(f"  กำลังสร้าง: {text}")
        try:
            tts = gTTS(text, lang='th')
            tts.save(filepath)
            generated += 1
            print(f"  [OK] บันทึกแล้ว: {filename}")
            generated += 1
        except Exception as e:
            print(f"  [ERROR] เกิดข้อผิดพลาด: {e}")
    else:
        print(f"  ข้าม (มีอยู่แล้ว): {text[:40]}...")
        skipped += 1

print(f"\nเสร็จสิ้น — สร้างใหม่ {generated} ไฟล์, ข้าม {skipped} ไฟล์")
print("โปรแกรม BPTOHIS พร้อมทำงานแบบออฟไลน์แล้ว [OK]")
