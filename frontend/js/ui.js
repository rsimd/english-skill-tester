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
        const score = Math.round(data.final_score || 0);
        const hue = (score / 100) * 120;
        const scoreColor = `hsl(${hue}, 70%, 45%)`;

        // ── 1. 総合スコア ──────────────────────────────────
        let html = `
            <div class="eval-score-header">
                <div class="eval-big-score" style="color:${scoreColor}">${score}</div>
                <div class="eval-score-sub">
                    <span class="eval-score-label">/ 100</span>
                </div>
                <div class="eval-estimates">
                    <span class="eval-estimate-badge">TOEIC <strong>~${data.toeic_estimate}</strong></span>
                    <span class="eval-estimate-badge">IELTS <strong>~${data.ielts_estimate}</strong></span>
                </div>
            </div>`;

        // ── 2. 各軸スコア ──────────────────────────────────
        const axes = [
            { key: 'vocabulary',        label: '語彙' },
            { key: 'grammar',           label: '文法' },
            { key: 'fluency',           label: '流暢さ' },
            { key: 'comprehension',     label: '理解力' },
            { key: 'coherence',         label: '一貫性' },
            { key: 'pronunciation_proxy', label: '発音' },
        ];
        const axesWithData = axes.filter(a => data[a.key] != null);
        if (axesWithData.length) {
            html += `<div class="eval-section">
                <h3 class="eval-section-title">各軸スコア</h3>
                <div class="eval-score-bars">`;
            axesWithData.forEach(({ key, label }) => {
                const val = Math.round(data[key]);
                const h = (val / 100) * 120;
                html += `
                    <div class="eval-bar-item">
                        <label class="eval-bar-label">${label}</label>
                        <div class="eval-bar-track">
                            <div class="eval-bar-fill" style="width:${val}%;background:hsl(${h},65%,50%)"></div>
                        </div>
                        <span class="eval-bar-val">${val}</span>
                    </div>`;
            });
            html += `</div></div>`;
        }

        // ── 3. セッション統計 ──────────────────────────────
        if (data.session_duration != null || data.utterance_count != null) {
            const dur = data.session_duration || 0;
            const mm = String(Math.floor(dur / 60)).padStart(2, '0');
            const ss = String(dur % 60).padStart(2, '0');
            html += `<div class="eval-section">
                <h3 class="eval-section-title">セッション統計</h3>
                <div class="eval-stats-row">
                    <div class="eval-stat">
                        <span class="eval-stat-icon">⏱</span>
                        <span class="eval-stat-val">${mm}:${ss}</span>
                        <span class="eval-stat-label">会話時間</span>
                    </div>
                    <div class="eval-stat">
                        <span class="eval-stat-icon">💬</span>
                        <span class="eval-stat-val">${data.utterance_count || 0}</span>
                        <span class="eval-stat-label">発話回数</span>
                    </div>
                    <div class="eval-stat">
                        <span class="eval-stat-icon">🔤</span>
                        <span class="eval-stat-val">${data.filler_rate != null ? data.filler_rate + '%' : '--'}</span>
                        <span class="eval-stat-label">フィラー率</span>
                    </div>
                </div>
            </div>`;
        }

        // ── 4. 総合評価 ────────────────────────────────────
        if (data.summary) {
            html += `<div class="eval-section">
                <h3 class="eval-section-title">総合評価</h3>
                <p class="eval-summary">${this._escapeHtml(data.summary)}</p>
            </div>`;
        }

        // ── 5. 良かった点 ──────────────────────────────────
        if (data.strengths && data.strengths.length) {
            html += `<div class="eval-section">
                <h3 class="eval-section-title">良かった点</h3>
                <ul class="eval-list eval-list-good">
                    ${data.strengths.map(s => `<li>${this._escapeHtml(s)}</li>`).join('')}
                </ul>
            </div>`;
        }

        // ── 6. 改善ポイント ────────────────────────────────
        if (data.weaknesses && data.weaknesses.length) {
            html += `<div class="eval-section">
                <h3 class="eval-section-title">改善ポイント</h3>
                <ul class="eval-list eval-list-bad">
                    ${data.weaknesses.map(w => `<li>${this._escapeHtml(w)}</li>`).join('')}
                </ul>
            </div>`;
        }

        // ── 7. 修正例 ──────────────────────────────────────
        if (data.example_corrections && data.example_corrections.length) {
            html += `<div class="eval-section">
                <h3 class="eval-section-title">修正例</h3>
                <div class="eval-corrections">
                    ${data.example_corrections.map(c => {
                        const orig = c.original ? this._escapeHtml(c.original) : '';
                        const corrected = c.corrected ? this._escapeHtml(c.corrected) : '';
                        const explanation = c.explanation ? this._escapeHtml(c.explanation) : '';
                        return `<div class="eval-correction-item">
                            <div class="eval-correction-orig">✗ ${orig}</div>
                            <div class="eval-correction-fix">✓ ${corrected}</div>
                            ${explanation ? `<div class="eval-correction-note">${explanation}</div>` : ''}
                        </div>`;
                    }).join('')}
                </div>
            </div>`;
        }

        // ── 8. ハイライト付き会話ログ ──────────────────────
        if (data.transcript && data.transcript.length) {
            html += `<div class="eval-section">
                <h3 class="eval-section-title">会話ログ（ハイライト付き）</h3>
                <div class="eval-legend">
                    <span class="hl-chip hl-grammar">文法</span>
                    <span class="hl-chip hl-filler">フィラー</span>
                    <span class="hl-chip hl-vocab">高度語彙</span>
                </div>
                <div class="eval-transcript">`;
            data.transcript.forEach(u => {
                const isUser = u.role === 'user';
                const speaker = isUser ? 'あなた' : 'AI';
                const cls = isUser ? 'eval-turn-user' : 'eval-turn-ai';
                let textHtml = this._renderHighlightedText(u.text, u.highlights || []);
                html += `<div class="eval-turn ${cls}">
                    <span class="eval-speaker">${speaker}</span>
                    <span class="eval-turn-text">${textHtml}</span>
                </div>`;
            });
            html += `</div></div>`;
        }

        this.feedbackContent.innerHTML = html;
        this.feedbackOverlay.classList.remove('hidden');
    }

    _renderHighlightedText(text, highlights) {
        if (!highlights || !highlights.length) {
            return this._escapeHtml(text);
        }

        // Build a set of words with their highlight types
        const hlMap = {};
        highlights.forEach(h => {
            if (h.word) {
                const w = h.word.toLowerCase();
                if (!hlMap[w]) hlMap[w] = [];
                hlMap[w].push(h.type);
            }
        });

        // Replace words in text, longest match first (simple word boundary replace)
        const escaped = this._escapeHtml(text);
        return escaped.replace(/\b([a-zA-Z']+)\b/g, (match) => {
            const types = hlMap[match.toLowerCase()];
            if (!types || !types.length) return match;
            // Priority: grammar > filler > advanced_vocab
            if (types.includes('grammar')) {
                return `<span class="hl hl-grammar" title="文法エラー">${match}</span>`;
            }
            if (types.includes('filler')) {
                return `<span class="hl hl-filler" title="フィラー語">${match}</span>`;
            }
            if (types.includes('advanced_vocab')) {
                return `<span class="hl hl-vocab" title="高度語彙">${match}</span>`;
            }
            return match;
        });
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
