/**
 * Main application logic - connects WebSocket, UI, and character controller.
 */

(function () {
    'use strict';

    const ws = new WebSocketClient();
    const ui = new UIController();
    let sessionActive = false;

    function getOrCreateUserId() {
        let userId = localStorage.getItem('english_skill_tester_user_id');
        if (!userId) {
            userId = (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36));
            localStorage.setItem('english_skill_tester_user_id', userId);
        }
        return userId;
    }

    // ---- WebSocket event handlers ----

    ws.on('connected', () => {
        ui.setConnectionStatus(true);
    });

    ws.on('disconnected', () => {
        ui.setConnectionStatus(false);
        if (sessionActive) {
            sessionActive = false;
            ui.setSessionActive(false);
        }
    });

    ws.on('session_state', (data) => {
        if (data.status === 'active') {
            sessionActive = true;
            ui.setSessionActive(true);
            document.getElementById('force-stop-btn').style.display = 'block';
            document.getElementById('loading-indicator').style.display = 'none';
        } else if (data.status === 'completed') {
            sessionActive = false;
            ui.setSessionActive(false);
            document.getElementById('force-stop-btn').style.display = 'none';
        }
    });

    ws.on('session_end', () => {
        sessionActive = false;
        ui.setSessionActive(false);
        document.getElementById('force-stop-btn').style.display = 'none';
    });

    ws.on('transcript', (data) => {
        ui.addTranscript(data.role, data.text);
    });

    ws.on('score_update', (data) => {
        ui.updateScores(data);
        if (data.cefr) {
            const badge = document.getElementById('level-badge');
            if (badge) {
                const cefrLabels = {A1:'A1(初心者)', A2:'A2(初級)', B1:'B1(中級)', B2:'B2(中上級)', C1:'C1(上級)', C2:'C2(最上級)'};
                badge.textContent = cefrLabels[data.cefr] || data.cefr;
            }
        }
    });

    ws.on('level_change', (data) => {
        console.log('Level changed to:', data.level);
    });

    ws.on('character_action', (data) => {
        if (window.CharacterController) {
            if (data.action_type === 'expression') {
                window.CharacterController.setExpression(data.value);
            } else if (data.action_type === 'gesture') {
                window.CharacterController.playGesture(data.value);
            }
        }
    });

    // Audio level for lip sync
    ws.on('audio_level', (data) => {
        if (window.CharacterController && window.CharacterController.setAudioLevel) {
            window.CharacterController.setAudioLevel(data.level || 0);
        }
    });

    // AI speaking state for lip sync
    ws.on('ai_speaking', (data) => {
        if (window.CharacterController && window.CharacterController.setAiSpeaking) {
            window.CharacterController.setAiSpeaking(data.speaking || false);
        }
    });

    ws.on('feedback', (data) => {
        ui.showFeedback(data);
    });

    // ---- Button handlers ----

    ui.btnStart.addEventListener('click', () => {
        if (!sessionActive) {
            const deviceId = document.getElementById('input-device')?.value || null;
            const selfReportedLevel = document.getElementById('self-reported-level')?.value || null;
            const userId = getOrCreateUserId();
            ws.send('start_session', { device_id: deviceId, user_id: userId, self_reported_level: selfReportedLevel || null });
            document.getElementById('loading-indicator').style.display = 'flex';
        }
    });

    ui.btnStop.addEventListener('click', () => {
        if (sessionActive) {
            ws.send('stop_session');
        }
    });

    // ---- Force stop ----

    function forceStopSession() {
        ws.send('force_stop');
        document.getElementById('force-stop-btn').style.display = 'none';
    }
    document.getElementById('force-stop-btn').addEventListener('click', forceStopSession);

    // ---- Model switching ----

    const btnModel = document.getElementById('btn-change-model');
    const vrmInput = document.getElementById('vrm-upload');

    if (btnModel && vrmInput) {
        btnModel.addEventListener('click', () => vrmInput.click());
        vrmInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            if (!file.name.toLowerCase().endsWith('.vrm')) {
                alert('VRMファイルを選択してください');
                return;
            }
            if (file.size > 50 * 1024 * 1024) { // 50MB上限
                alert('ファイルサイズが大きすぎます（50MB以下）');
                return;
            }
            const url = URL.createObjectURL(file);
            try {
                await window.CharacterController.loadModel(url);
                document.getElementById('model-name').textContent = file.name;
            } catch (err) {
                console.error('Model load failed:', err);
                alert('VRMの読み込みに失敗しました: ' + err.message);
                // Reload default model
                await window.CharacterController.loadModel('/models/avatar.vrm');
            } finally {
                URL.revokeObjectURL(url);
                vrmInput.value = ''; // Reset for same file re-upload
            }
        });
    }

    // ---- Audio device selection ----

    async function loadAudioDevices() {
        try {
            const res = await fetch('/api/audio/devices');
            const data = await res.json();
            const inputSel = document.getElementById('input-device');
            const outputSel = document.getElementById('output-device');
            data.devices.forEach(dev => {
                if (dev.max_input_channels > 0) {
                    const opt = new Option(dev.name, dev.index);
                    if (dev.index === data.default_input) opt.selected = true;
                    inputSel.appendChild(opt);
                }
                if (dev.max_output_channels > 0) {
                    const opt = new Option(dev.name, dev.index);
                    if (dev.index === data.default_output) opt.selected = true;
                    outputSel.appendChild(opt);
                }
            });
        } catch (e) {
            console.warn('Failed to load audio devices:', e);
        }
    }

    // ---- Initialize ----

    function init() {
        ws.connect();
        loadAudioDevices();

        // Initialize 3D character — retry until module script has loaded
        function tryInitCharacter() {
            if (window.CharacterController) {
                window.CharacterController.init();
            } else {
                setTimeout(tryInitCharacter, 200);
            }
        }
        setTimeout(tryInitCharacter, 200);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(init, 50));
    } else {
        setTimeout(init, 50);
    }

})();
