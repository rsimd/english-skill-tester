/**
 * Main application logic - connects WebSocket, UI, and character controller.
 */

(function () {
    'use strict';

    const ws = new WebSocketClient();
    const ui = new UIController();
    let sessionActive = false;

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
        } else if (data.status === 'completed') {
            sessionActive = false;
            ui.setSessionActive(false);
        }
    });

    ws.on('transcript', (data) => {
        ui.addTranscript(data.role, data.text);
    });

    ws.on('score_update', (data) => {
        ui.updateScores(data);
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
            ws.send('start_session');
        }
    });

    ui.btnStop.addEventListener('click', () => {
        if (sessionActive) {
            ws.send('stop_session');
        }
    });

    // ---- Initialize ----

    function init() {
        ws.connect();

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
