// --- DOM Elements ---
const statusCard = document.getElementById('status-card');
const infoCard = document.getElementById('info-card');
const logContent = document.getElementById('log-content');
const bpStatus = document.getElementById('bp-status');
const bpResult = document.getElementById('bp-result');

const valCid = document.getElementById('val-cid');
const valName = document.getElementById('val-name');
const valAddress = document.getElementById('val-address');
const valSys = document.getElementById('val-sys');
const valDia = document.getElementById('val-dia');
const valPulse = document.getElementById('val-pulse');
const logStatus = document.getElementById('log-status');

// Summary panel elements
const summaryDate  = document.getElementById('summary-date');
const summaryTotal = document.getElementById('summary-total');
const summaryRows  = document.getElementById('summary-rows');
const btnRefreshSummary = document.getElementById('btn-refresh-summary');

// Settings Modal elements
const settingsModal = document.getElementById('settings-modal');
const btnSettings = document.getElementById('btn-settings');
const btnCloseSettings = document.getElementById('btn-close-settings');
const btnSaveSettings = document.getElementById('btn-save-settings');
const btnRefreshPorts = document.getElementById('btn-refresh-ports');
const btnTestSubmit   = document.getElementById('btn-test-submit');
const inputUrl        = document.getElementById('input-url');
const inputGithubRepo = document.getElementById('input-github-repo');
const selectPort      = document.getElementById('select-port');
const btnClear        = document.getElementById('btn-clear');

// Update banner
const updateBanner      = document.getElementById('update-banner');
const updateMessage     = document.getElementById('update-message');
const updateProgressWrap = document.getElementById('update-progress-wrap');
const updateProgressBar = document.getElementById('update-progress-bar');
const btnApplyUpdate    = document.getElementById('btn-apply-update');

const toast = document.getElementById('toast');
const toastIcon = document.getElementById('toast-icon');
const toastMessage = document.getElementById('toast-message');

let evtSource = null;

// --- Utility Functions ---
function getTimestamp() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}

function addLog(message, isHTML = false) {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const timeSpan = `<span class="log-time">[${getTimestamp()}]</span>`;

    if (isHTML) {
        entry.innerHTML = `${timeSpan} ${message}`;
    } else {
        entry.innerHTML = `${timeSpan} ${message.replace(/</g, "&lt;").replace(/>/g, "&gt;")}`;
    }

    logContent.appendChild(entry);
    logContent.scrollTop = logContent.scrollHeight;
}

function showToast(message, type = 'info') {
    toastMessage.textContent = message;

    toastIcon.className = 'ph';
    if (type === 'success') {
        toastIcon.classList.add('ph-check-circle', 'text-success');
    } else if (type === 'error') {
        toastIcon.classList.add('ph-warning-circle', 'text-danger');
    } else {
        toastIcon.classList.add('ph-info', 'text-primary');
    }

    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// --- App Logic ---

function resetUI() {
    statusCard.style.display = 'flex';
    infoCard.style.display = 'none';
    bpResult.style.display = 'none';
    bpStatus.style.display = 'flex';
    logStatus.innerHTML = '';

    valCid.textContent = '-';
    valName.textContent = '-';
    valAddress.textContent = '-';
}

function startSSE() {
    if (evtSource) {
        evtSource.close();
    }

    evtSource = new EventSource('/api/events');

    evtSource.onmessage = function (e) {
        const data = JSON.parse(e.data);

        if (data.type === 'log') {
            addLog(data.message);
        } else if (data.type === 'card_removed') {
            resetUI();
            addLog("บัตรถูกถอดออก");
        } else if (data.type === 'card_inserted') {
            // Found a card
            statusCard.style.display = 'none';
            infoCard.style.display = 'flex';
            bpResult.style.display = 'none';
            bpStatus.style.display = 'flex';
            logStatus.innerHTML = '';

            let rawCid = data.data.cid || '-';
            let rawName = data.data.name || '-';
            let maskedCid = '-';
            let maskedName = '-';

            if (rawCid !== '-') {
                // Masking CID: 1234567890123 -> 1-2345-xxxxx-xx-3
                maskedCid = rawCid.substring(0, 1) + '-' + rawCid.substring(1, 5) + '-xxxxx-xx-' + rawCid.substring(12, 13);
            }

            if (rawName !== '-') {
                // Masking Name: สมชาย มั่งมี -> สมชาย ม********
                let parts = rawName.trim().split(/\s+/);
                if (parts.length > 1) {
                    let fName = parts[0];
                    let lName = parts.slice(1).join(' ');
                    if (lName.length > 1) {
                        maskedName = fName + ' ' + lName.charAt(0) + '*'.repeat(lName.length - 1);
                    } else {
                        maskedName = fName + ' *';
                    }
                } else {
                    maskedName = rawName.charAt(0) + '*'.repeat(rawName.length - 1);
                }
            }

            valCid.textContent = maskedCid;
            valName.textContent = maskedName;
            valAddress.textContent = data.data.address || '-';

            addLog(`พบบัตร: ${data.data.name}`);
        } else if (data.type === 'bp_result') {
            const bp = data.data;
            bpStatus.style.display = 'none';
            bpResult.style.display = 'flex';

            valSys.textContent = bp.bps;
            valDia.textContent = bp.bpd;
            valPulse.textContent = bp.pulse;

            // Health color classification
            const sys = parseInt(bp.bps);
            const dia = parseInt(bp.bpd);

            let color = 'var(--text-900)';
            let summaryClass = 'status-normal';
            let summaryText = '';

            if (sys >= 180 || dia >= 110) {
                color = 'var(--danger-dark)';
                summaryClass = 'status-high';
                summaryText = '<i class="ph ph-warning-octagon"></i> โรคความดันโลหิตสูง ระดับ 3 — ควรรีบพบแพทย์ทันที';
            } else if (sys >= 160 || dia >= 100) {
                color = 'var(--danger)';
                summaryClass = 'status-high';
                summaryText = '<i class="ph ph-warning"></i> โรคความดันโลหิตสูง ระดับ 2 — ควรรีบพบแพทย์';
            } else if (sys >= 140 || dia >= 90) {
                color = '#ea580c';
                summaryClass = 'status-risk';
                summaryText = '<i class="ph ph-warning"></i> โรคความดันโลหิตสูง ระดับ 1 — ควรพบแพทย์เพื่อวินิจฉัย';
            } else if (sys >= 130 || dia >= 85) {
                color = 'var(--warning)';
                summaryClass = 'status-risk';
                summaryText = '<i class="ph ph-info"></i> ความดันสูงกว่าปกติ — ควรปรับเปลี่ยนพฤติกรรมสุขภาพ';
            } else if (sys >= 120 || dia >= 80) {
                color = 'var(--info, #0ea5e9)';
                summaryClass = 'status-normal';
                summaryText = '<i class="ph ph-check-circle"></i> ความดันปกติ — ควบคุมอาหาร ออกกำลังกาย วัดความดันสม่ำเสมอ';
            } else if (sys < 90 || dia < 60) {
                color = 'var(--low-bp)';
                summaryClass = 'status-low';
                summaryText = '<i class="ph ph-arrow-down"></i> ความดันต่ำ — ควรดื่มน้ำและพักผ่อน';
            } else {
                color = 'var(--success)';
                summaryClass = 'status-normal';
                summaryText = '<i class="ph ph-check-circle"></i> ความดันเหมาะสม — สุขภาพดีเยี่ยม!';
            }

            valSys.style.color = color;
            valDia.style.color = color;

            // Pulse color classification
            const pls = parseInt(bp.pulse);
            let pulseColor = 'var(--text-900)';

            if (pls > 120) {
                pulseColor = 'var(--danger-dark)';
            } else if (pls >= 101 && pls <= 120) {
                pulseColor = '#ea580c';
            } else if (pls >= 60 && pls <= 100) {
                pulseColor = 'var(--success)';
            } else if (pls >= 50 && pls < 60) {
                pulseColor = 'var(--warning)';
            } else {
                pulseColor = 'var(--low-bp)';
            }

            valPulse.style.color = pulseColor;

            // Apply summary banner
            logStatus.className = 'bp-summary ' + summaryClass;
            logStatus.innerHTML = summaryText;

            addLog(`วัดความดันสำเร็จ: ${bp.bps}/${bp.bpd} ชีพจร: ${bp.pulse}`, true);
        } else if (data.type === 'sheet_status') {
            if (data.data && data.data.success) {
                logStatus.className = 'bp-summary status-saved';
                logStatus.innerHTML = '<i class="ph ph-cloud-check"></i> บันทึกข้อมูลไปที่ Google Sheets สำเร็จ';
                addLog('บันทึกข้อมูลไปที่ Google Sheets สำเร็จ');
            } else {
                logStatus.className = 'bp-summary status-error';
                logStatus.innerHTML = '<i class="ph ph-cloud-slash"></i> ไม่สามารถบันทึกข้อมูลได้ โปรดตรวจสอบ URL';
                addLog('ไม่สามารถบันทึกข้อมูลได้ โปรดตรวจสอบ URL');
            }
        } else if (data.type === 'daily_summary_update') {
            fetchDailySummary();
        } else if (data.type === 'update_available') {
            // พบเวอร์ชันใหม่
            updateBanner.style.display = 'flex';
            updateBanner.className = 'update-banner update-info';
            updateMessage.textContent = `พบเวอร์ชันใหม่ v${data.data.latest} (ปัจจุบัน v${data.data.current}) — กำลังดาวน์โหลด...`;
            updateProgressWrap.style.display = 'block';
            btnApplyUpdate.style.display = 'none';
        } else if (data.type === 'update_progress') {
            const pct = data.data.percent || 0;
            updateBanner.style.display = 'flex';
            updateMessage.textContent = data.message;
            updateProgressWrap.style.display = 'block';
            updateProgressBar.style.width = pct + '%';
        } else if (data.type === 'update_ready') {
            // ดาวน์โหลดเสร็จ รอ user กด
            updateBanner.className = 'update-banner update-success';
            updateMessage.textContent = `พร้อมอัปเดตเป็น v${data.data.new_version} — กดปุ่มเพื่อรีสตาร์ท`;
            updateProgressWrap.style.display = 'none';
            btnApplyUpdate.style.display = 'inline-flex';
            // อัตโนมัติหลัง 60 วินาที
            let countdown = 60;
            const timer = setInterval(() => {
                countdown--;
                updateMessage.textContent = `พร้อมอัปเดตเป็น v${data.data.new_version} — รีสตาร์ทอัตโนมัติใน ${countdown} วินาที`;
                if (countdown <= 0) {
                    clearInterval(timer);
                    applyUpdate();
                }
            }, 1000);
        }
    };

    evtSource.onerror = function (e) {
        console.error("EventSource failed.", e);
        // It will auto reconnect, but we can log
    };
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const readerText = document.getElementById('sub-status-text');
        const kioskIcon = document.querySelector('#status-card .kiosk-icon');
        const readerBadge = document.getElementById('reader-badge');

        if (data.readers.length > 0) {
            if (readerText) readerText.textContent = 'เครื่องพร้อมใช้งาน';
            document.getElementById('status-text').textContent = 'กรุณาเสียบบัตรประชาชน';
            if (kioskIcon) {
                kioskIcon.querySelector('i').className = 'ph ph-identification-card';
                kioskIcon.classList.remove('searching');
            }
            if (readerBadge) {
                readerBadge.classList.remove('warning');
                readerBadge.innerHTML = '<i class="ph ph-check-circle"></i><span>เครื่องอ่านบัตรพร้อม</span>';
            }
        } else {
            if (readerText) readerText.textContent = 'ไม่พบเครื่องอ่านบัตร';
            document.getElementById('status-text').textContent = 'กำลังค้นหาเครื่องอ่านบัตร...';
            if (kioskIcon) {
                kioskIcon.querySelector('i').className = 'ph ph-magnifying-glass';
                kioskIcon.classList.add('searching');
            }
            if (readerBadge) {
                readerBadge.classList.add('warning');
                readerBadge.innerHTML = '<i class="ph ph-warning-circle"></i><span>ไม่พบเครื่องอ่านบัตร</span>';
            }
        }
    } catch (e) {
        console.error('Error fetching status', e);
    }
}

async function loadConfig() {
    try {
        const res    = await fetch('/api/config');
        const config = await res.json();
        inputUrl.value        = config.web_app_url;
        if (inputGithubRepo) inputGithubRepo.value = config.github_repo || '';
        await refreshPorts(config.com_port);
    } catch (e) {
        console.error("Error loading config", e);
    }
}

async function refreshPorts(selectedPort = null) {
    try {
        const res = await fetch('/api/ports');
        const ports = await res.json();

        selectPort.innerHTML = '<option value="Auto">Auto</option>';
        ports.forEach(port => {
            const opt = document.createElement('option');
            opt.value = port;
            opt.textContent = port;
            selectPort.appendChild(opt);
        });

        if (selectedPort && ports.includes(selectedPort)) {
            selectPort.value = selectedPort;
        } else if (selectedPort === 'Auto' || !selectedPort) {
            selectPort.value = 'Auto';
        } else {
            // Selected port is not in list but was saved
            const opt = document.createElement('option');
            opt.value = selectedPort;
            opt.textContent = selectedPort + " (Not Found)";
            selectPort.appendChild(opt);
            selectPort.value = selectedPort;
        }
    } catch (e) {
        console.error("Error fetching ports", e);
    }
}

async function saveConfig() {
    const data = {
        web_app_url: inputUrl.value,
        com_port:    selectPort.value,
        github_repo: inputGithubRepo ? inputGithubRepo.value.trim() : '',
    };
    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            showToast('บันทึกการตั้งค่าเรียบร้อยแล้ว', 'success');
            settingsModal.style.display = 'none';
        }
    } catch (e) {
        showToast('เกิดข้อผิดพลาดในการบันทึก', 'error');
    }
}

async function testSubmit() {
    if (!inputUrl.value) {
        showToast('กรุณาใส่ Web App URL ก่อน', 'error');
        return;
    }

    btnTestSubmit.disabled = true;
    btnTestSubmit.innerHTML = '<i class="ph ph-spinner ph-spin"></i> กำลังส่ง...';

    try {
        const res = await fetch('/api/test_submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: inputUrl.value })
        });
        const result = await res.json();
        if (result.success) {
            showToast('ส่งข้อมูลทดสอบสำเร็จ', 'success');
        } else {
            showToast('ส่งข้อมูลทดสอบไม่สำเร็จ กรุณาตรวจสอบ URL', 'error');
        }
    } catch (e) {
        showToast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
        btnTestSubmit.disabled = false;
        btnTestSubmit.textContent = 'ทดสอบส่งข้อมูล';
    }
}

// --- Clock ---
function updateClock() {
    const now = new Date();
    const days = ['อาทิตย์', 'จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์'];
    const d = now.getDate();
    const m = now.getMonth() + 1;
    const y = now.getFullYear() + 543;
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const el = document.getElementById('kiosk-clock');
    if (el) el.textContent = `วัน${days[now.getDay()]}ที่ ${d}/${m}/${y} เวลา ${time} น.`;
}

// --- Event Listeners ---
btnSettings.addEventListener('click', () => {
    settingsModal.style.display = 'flex';
    loadConfig();
});

btnCloseSettings.addEventListener('click', () => {
    settingsModal.style.display = 'none';
});

settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) settingsModal.style.display = 'none';
});

btnSaveSettings.addEventListener('click', saveConfig);
btnRefreshPorts.addEventListener('click', () => refreshPorts());
btnTestSubmit.addEventListener('click', testSubmit);

btnClear.addEventListener('click', () => {
    logContent.innerHTML = '';
    showToast('ล้างข้อมูล Log เรียบร้อย', 'info');
});

// --- Daily Summary ---
async function fetchDailySummary() {
    try {
        const res = await fetch('/api/daily_summary');
        const data = await res.json();

        // Update date & total
        if (summaryDate) {
            const d = new Date(data.date + 'T00:00:00');
            summaryDate.textContent = `${d.getDate()}/${d.getMonth()+1}/${d.getFullYear()+543}`;
        }
        if (summaryTotal) summaryTotal.textContent = data.total || 0;

        if (!summaryRows) return;

        const tambons = data.tambons || [];

        if (tambons.length === 0) {
            summaryRows.innerHTML = `
                <div class="summary-empty">
                    <i class="ph ph-database"></i>
                    <span>ยังไม่มีข้อมูลวันนี้</span>
                </div>`;
            return;
        }

        summaryRows.innerHTML = '';
        tambons.forEach(t => {
            const total = t.total || 1; // avoid div/0
            const pct = (v) => ((v / total) * 100).toFixed(1);

            // Only show non-zero categories
            const cats = [];
            if (t.optimal  > 0) cats.push(`<span class="cat-dot optimal">${t.optimal} เหมาะสม</span>`);
            if (t.normal   > 0) cats.push(`<span class="cat-dot normal">${t.normal} ปกติ</span>`);
            if (t.risk     > 0) cats.push(`<span class="cat-dot risk">${t.risk} สูงกว่าปกติ</span>`);
            if (t.elevated > 0) cats.push(`<span class="cat-dot elevated">${t.elevated} สูง ระดับ1</span>`);
            if (t.sys_only > 0) cats.push(`<span class="cat-dot elevated">${t.sys_only} สูงตัวบน</span>`);
            if (t.dia_only > 0) cats.push(`<span class="cat-dot elevated">${t.dia_only} สูงตัวล่าง</span>`);
            if (t.high     > 0) cats.push(`<span class="cat-dot high">${t.high} สูง ระดับ2</span>`);
            if (t.crisis   > 0) cats.push(`<span class="cat-dot crisis">${t.crisis} สูง ระดับ3</span>`);
            if (t.low      > 0) cats.push(`<span class="cat-dot low">${t.low} ต่ำ</span>`);

            // รวม elevated+sys_only+dia_only เข้าด้วยกันสำหรับ bar
            const elevatedTotal = (t.elevated||0) + (t.sys_only||0) + (t.dia_only||0);

            const block = document.createElement('div');
            block.className = 'tambon-block';
            block.innerHTML = `
                <div class="tambon-name-row">
                    <span class="tambon-name">ต.${t.tambon}</span>
                    <span class="tambon-count-badge">${t.total} ราย</span>
                </div>
                <div class="tambon-bar-wrap">
                    ${(t.optimal||0) > 0 ? `<div class="bar-seg bar-optimal"  style="width:${pct(t.optimal)}%"></div>` : ''}
                    ${(t.normal||0)  > 0 ? `<div class="bar-seg bar-normal"   style="width:${pct(t.normal)}%"></div>` : ''}
                    ${elevatedTotal  > 0 ? `<div class="bar-seg bar-elevated" style="width:${pct(elevatedTotal)}%"></div>` : ''}
                    ${(t.risk||0)    > 0 ? `<div class="bar-seg bar-risk"     style="width:${pct(t.risk)}%"></div>` : ''}
                    ${(t.high||0)    > 0 ? `<div class="bar-seg bar-high"     style="width:${pct(t.high)}%"></div>` : ''}
                    ${(t.crisis||0)  > 0 ? `<div class="bar-seg bar-crisis"   style="width:${pct(t.crisis)}%"></div>` : ''}
                    ${(t.low||0)     > 0 ? `<div class="bar-seg bar-low"      style="width:${pct(t.low)}%"></div>` : ''}
                </div>
                <div class="tambon-cats">${cats.join('')}</div>
            `;
            summaryRows.appendChild(block);
        });
    } catch (e) {
        console.error('Summary fetch error', e);
    }
}

btnRefreshSummary.addEventListener('click', () => {
    fetchDailySummary();
    showToast('รีเฟรชข้อมูลสรุปแล้ว', 'info');
});

// --- Apply Update ---
async function applyUpdate() {
    try {
        await fetch('/api/apply_update', { method: 'POST' });
        updateMessage.textContent = 'กำลังรีสตาร์ท...';
    } catch(e) {
        console.error(e);
    }
}

if (btnApplyUpdate) {
    btnApplyUpdate.addEventListener('click', applyUpdate);
}

// Init
window.addEventListener('load', () => {
    addLog("ระบบพร้อมทำงาน");
    fetchStatus();
    startSSE();
    updateClock();
    fetchDailySummary();

    setInterval(fetchStatus, 5000);
    setInterval(updateClock, 10000);
    setInterval(fetchDailySummary, 30000); // รีเฟรชสรุปทุก 30 วินาที
});
