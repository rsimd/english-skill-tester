/**
 * UI controller for score display, transcript, and controls.
 */
class UIController {
    constructor() {
        this.overallScore = document.getElementById('overall-score');
        this.levelBadge = document.getElementById('level-badge');
        this.toeicEstimate = document.getElementById('toeic-estimate');
        this.ieltsEstimate = document.getElementById('ielts-estimate');

        this.bars = {
            vocabulary: { bar: document.getElementById('bar-vocabulary'), val: document.getElementById('val-vocabulary') },
            grammar: { bar: document.getElementById('bar-grammar'), val: document.getElementById('val-grammar') },
            fluency: { bar: document.getElementById('bar-fluency'), val: document.getElementById('val-fluency') },
            comprehension: { bar: document.getElementById('bar-comprehension'), val: document.getElementById('val-comprehension') },
            coherence: { bar: document.getElementById('bar-coherence'), val: document.getElementById('val-coherence') },
        };

        this.transcript = document.getElementById('transcript');

        this.btnStart = document.getElementById('btn-start');
        this.btnStop = document.getElementById('btn-stop');
        this.timer = document.getElementById('timer');
        this.connectionStatus = document.getElementById('connection-status');

        this.feedbackOverlay = document.getElementById('feedback-overlay');
        this.feedbackContent = document.getElementById('feedback-content');
        this.btnCloseFeedback = document.getElementById('btn-close-feedback');
        this.btnReview = document.getElementById('btn-review');

        this._timerInterval = null;
        this._startTime = null;

        if (this.btnCloseFeedback) {
            this.btnCloseFeedback.addEventListener('click', () => this.hideFeedback());
        }
    }

    updateScores(data) {
        this.overallScore.textContent = Math.round(data.overall);
        this.levelBadge.textContent = data.level;
        this.toeicEstimate.textContent = data.toeic_estimate;
        this.ieltsEstimate.textContent = data.ielts_estimate;

        const hue = (data.overall / 100) * 120;
        this.overallScore.style.color = `hsl(${hue}, 70%, 45%)`;

        const components = ['vocabulary', 'grammar', 'fluency', 'comprehension', 'coherence'];
        components.forEach(name => {
            const value = data[name] || 50;
            if (this.bars[name]) {
                this.bars[name].bar.style.width = `${value}%`;
                this.bars[name].val.textContent = Math.round(value);
            }
        });
    }

    addTranscript(role, text) {
        const entry = document.createElement('div');
        entry.className = `transcript-entry ${role}`;

        const speaker = document.createElement('span');
        speaker.className = 'speaker';
        speaker.textContent = role === 'user' ? 'You' : 'AI';

        const textEl = document.createElement('span');
        textEl.className = 'text';
        textEl.textContent = text;

        entry.appendChild(speaker);
        entry.appendChild(textEl);
        this.transcript.appendChild(entry);
        this.transcript.scrollTop = this.transcript.scrollHeight;
    }

    setConnectionStatus(connected) {
        if (connected) {
            this.connectionStatus.className = 'status-indicator connected';
            this.connectionStatus.querySelector('.label').textContent = 'Connected';
        } else {
            this.connectionStatus.className = 'status-indicator disconnected';
            this.connectionStatus.querySelector('.label').textContent = 'Disconnected';
        }
    }

    setSessionActive(active) {
        this.btnStart.disabled = active;
        this.btnStop.disabled = !active;

        if (active) {
            this._startTime = Date.now();
            this._timerInterval = setInterval(() => this._updateTimer(), 1000);
            this.transcript.innerHTML = '';
        } else {
            clearInterval(this._timerInterval);
            this._timerInterval = null;
        }
    }

    showFeedback(data) {
        let html = `
            <div class="feedback-score-display">
                <div class="big-score">${Math.round(data.final_score)}</div>
                <div>TOEIC ~${data.toeic_estimate} / IELTS ~${data.ielts_estimate}</div>
            </div>
        `;

        if (data.summary) {
            html += `<div class="feedback-section">
                <h3>総合評価</h3>
                <p>${this._escapeHtml(data.summary)}</p>
            </div>`;
        }

        if (data.strengths && data.strengths.length) {
            html += `<div class="feedback-section">
                <h3>良かった点</h3>
                <ul>${data.strengths.map(s => `<li>${this._escapeHtml(s)}</li>`).join('')}</ul>
            </div>`;
        }

        if (data.weaknesses && data.weaknesses.length) {
            html += `<div class="feedback-section">
                <h3>改善点</h3>
                <ul>${data.weaknesses.map(w => `<li>${this._escapeHtml(w)}</li>`).join('')}</ul>
            </div>`;
        }

        if (data.advice && data.advice.length) {
            html += `<div class="feedback-section">
                <h3>アドバイス</h3>
                <ul>${data.advice.map(a => `<li>${this._escapeHtml(a)}</li>`).join('')}</ul>
            </div>`;
        }

        if (data.example_corrections && data.example_corrections.length) {
            html += `<div class="feedback-section">
                <h3>修正例</h3>
                <ul>${data.example_corrections.map(c => {
                    const orig = c.original ? this._escapeHtml(c.original) : '';
                    const corrected = c.corrected ? this._escapeHtml(c.corrected) : '';
                    const explanation = c.explanation ? this._escapeHtml(c.explanation) : '';
                    return `<li>
                        <span style="color:var(--danger);text-decoration:line-through">${orig}</span>
                        → <strong>${corrected}</strong>
                        <br><small style="color:var(--text-secondary)">${explanation}</small>
                    </li>`;
                }).join('')}</ul>
            </div>`;
        }

        this.feedbackContent.innerHTML = html;
        this.feedbackOverlay.classList.remove('hidden');
    }

    hideFeedback() {
        this.feedbackOverlay.classList.add('hidden');
    }

    _updateTimer() {
        if (!this._startTime) return;
        const elapsed = Math.floor((Date.now() - this._startTime) / 1000);
        const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
        const secs = String(elapsed % 60).padStart(2, '0');
        this.timer.textContent = `${mins}:${secs}`;
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
