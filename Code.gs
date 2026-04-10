function doPost(e) {
  try {
    // กำหนด Google Sheet ที่ใช้งานปัจจุบัน
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // ==========================================
    // ตรวจสอบและสร้างหัวข้อคอลัมน์ให้อัตโนมัติ (ถ้ายาวไม่ถึงแถวแรก)
    // ==========================================
    if (sheet.getLastRow() === 0) {
      var headers = ["Timestamp", "CID", "Name", "Address", "SYS/BPS", "DIA/BPD", "Pulse"];
      sheet.appendRow(headers);
      
      // ออปชันตกแต่งหัวข้อ (ถ้าต้องการ)
      sheet.getRange("A1:G1").setFontWeight("bold").setBackground("#d0e2e5");
    }
    
    // แปลง JSON ที่ถูกส่งเข้ามา
    var data = JSON.parse(e.postData.contents);
    
    // ดึงข้อมูลแต่ละตัวแปร
    var timestamp = new Date();
    var cid = data.cid || "";
    var name = data.name || "";
    var address = data.address || "";
    var bps = data.bps || "";
    var bpd = data.bpd || "";
    var pulse = data.pulse || "";
    
    // เพิ่มข้อมูลลงในแถวใหม่
    sheet.appendRow([timestamp, cid, name, address, bps, bpd, pulse]);
    
    // สร้าง Response ส่งกลับไปที่ Python
    return ContentService.createTextOutput(JSON.stringify({"status": "success", "message": "Data recorded"}))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({"status": "error", "message": error.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
