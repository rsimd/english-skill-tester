# IMPLEMENTATION STRATEGY: cmd_002

**策定者**: 軍師 (gunshi)
**日時**: 2026-02-27
**目的**: VRM ジェスチャー・リップシンク修正 + モデル切り替え機能実装

---

## Phase 概要

| Phase | 内容 | 必要スキル | 並列可否 |
|-------|------|-----------|---------|
| Phase 1 | リップシンク修正（overrideMouth対策） | Frontend (Three.js/VRM) | — |
| Phase 2 | ルールベースジェスチャー + アメリカ人ジェスチャー8種 | Frontend + Backend | Phase 1完了後 |
| Phase 3 | VRMモデル動的切り替え | Frontend | Phase 1完了後（Phase 2と並列可） |

---

## Phase 1: リップシンク修正

### 目的
VRM expression（happy等）設定時にリップシンクが停止する問題を解決する。

### 修正内容

#### 1-A. overrideMouth 無効化 (`character.js`)

VRMモデルロード直後に，全 expression の overrideMouth/overrideBlink を解除:

```javascript
// loadVRM() 内，vrm 取得後に追加
function disableExpressionOverrides() {
    if (!vrm || !vrm.expressionManager) return;
    const expressions = vrm.expressionManager.expressions || [];
    expressions.forEach(expr => {
        // Prevent emotion expressions from blocking mouth/blink
        if (expr.overrideMouth !== undefined) {
            expr.overrideMouth = 'none';
        }
        if (expr.overrideBlink !== undefined) {
            expr.overrideBlink = 'none';
        }
    });
    console.log('Expression overrides disabled for lip sync compatibility');
}
```

**注意**: `@pixiv/three-vrm@3.3.3` における override プロパティ名は `overrideMouth` / `overrideBlink`。VRM 1.0 仕様準拠。

#### 1-B. Expression weight 制御 (`character.js`)

リップシンク活性時は expression weight を低減し，mouth shapes との干渉を最小化:

```javascript
function setExpression(expression) {
    if (fallbackMode) { /* ... */ return; }
    if (!vrm || !vrm.expressionManager) return;

    currentExpression = expression;

    // Reset emotion expressions
    ['happy', 'angry', 'sad', 'surprised', 'relaxed'].forEach(e =>
        vrm.expressionManager.setValue(e, 0));

    const preset = presetMap[expression];
    if (preset) {
        // Reduce weight during speech to prevent mouth override
        const weight = aiSpeaking ? 0.35 : 0.7;
        vrm.expressionManager.setValue(preset, weight);
    }
}
```

#### 1-C. aiSpeaking フラグの遅延解除 (`websocket.py`)

`response.done` イベント時に即座に `aiSpeaking=false` にせず，バッファ再生のための猶予時間を設ける:

```python
async def on_response_done(event: dict) -> None:
    # Wait for playback buffer to drain before stopping lip sync
    await asyncio.sleep(0.3)
    if not self._ai_speaking:  # Check if new response has started
        self._ai_speaking = False
        await self._send_to_browser({"type": "ai_speaking", "speaking": False})
        await self._send_to_browser({"type": "audio_level", "level": 0})
```

### 修正ファイル
- `frontend/js/character.js` (1-A, 1-B)
- `src/english_skill_tester/api/websocket.py` (1-C)

### テスト方法
1. セッション開始し，AI と 1分以上会話
2. リップシンクが途中で止まらないことを確認
3. ブラウザコンソールで "Expression overrides disabled" ログを確認
4. 表情変化時にもリップシンクが継続することを確認

---

## Phase 2: ルールベースジェスチャー + アメリカ人ジェスチャー8種

### 目的
AI function call に依存しない確実なジェスチャー発火と，文化的に適切なジェスチャーバリエーションを実装する。

### 2-A. ジェスチャー定義拡張 (`character.js`)

現行5種 → 13種（8種追加）:

| # | ジェスチャー名 | 意味（アメリカ文化） | ボーン操作 |
|---|--------------|-------------------|-----------|
| 1 | nod | 同意・理解 | head: rotation.x 往復 |
| 2 | wave | 挨拶・別れ | rightUpperArm: rotation.z 振動 |
| 3 | thumbs_up | 承認・良い | rightUpperArm+rightLowerArm |
| 4 | explain | 説明中 | 両腕広げ+微振動 |
| 5 | listen | 傾聴 | head: tilt + spine: lean |
| 6 | **shrug** | 分からない・仕方ない | 両肩上げ（両UpperArm rotation.z） |
| 7 | **thinking_pose** | 考え中 | 右手を顎に（rightUpperArm+rightLowerArm） |
| 8 | **open_palms** | 正直・受容 | 両腕前に+手のひら上 |
| 9 | **head_shake** | 否定 | head: rotation.y 往復 |
| 10 | **lean_forward** | 興味・集中 | spine: rotation.x 前傾 |
| 11 | **celebration** | 祝福・喜び | 両腕上げ+小振動 |
| 12 | **point** | 指摘・注目 | rightUpperArm+rightLowerArm 前方 |
| 13 | **idle_rest** | 待機ポーズ | 全ボーン → デフォルト位置に戻す |

### 2-B. 待機ポーズ (`character.js`)

手を下ろした自然な待機ポーズを実装。ジェスチャー終了後にこのポーズに遷移:

```javascript
function setIdlePose() {
    if (!vrm || !vrm.humanoid) return;
    // Reset all gesture bones to rest position
    const bones = ['rightUpperArm', 'rightLowerArm', 'leftUpperArm', 'leftLowerArm', 'spine'];
    bones.forEach(name => {
        const bone = vrm.humanoid.getNormalizedBoneNode(name);
        if (bone) {
            bone.rotation.set(0, 0, 0);
        }
    });
}
```

### 2-C. ルールベースジェスチャートリガー (`websocket.py`)

新しい `GestureController` クラスをバックエンドに追加:

```python
class GestureController:
    """Rule-based gesture triggering based on conversation events."""

    def __init__(self, send_fn):
        self._send = send_fn  # _send_to_browser
        self._last_gesture_time = 0
        self._min_interval = 3.0  # 最小ジェスチャー間隔（秒）

    async def on_session_start(self):
        await self._trigger("wave")

    async def on_user_finished_speaking(self):
        await self._trigger("nod")

    async def on_ai_response_long(self):
        """AI応答が2文以上の時"""
        gesture = random.choice(["explain", "open_palms", "point"])
        await self._trigger(gesture)

    async def on_high_score(self):
        gesture = random.choice(["thumbs_up", "celebration"])
        await self._trigger(gesture)

    async def on_silence(self):
        """5秒以上沈黙"""
        await self._trigger("listen")

    async def on_question_asked(self):
        await self._trigger("thinking_pose")

    async def _trigger(self, gesture):
        now = time.time()
        if now - self._last_gesture_time < self._min_interval:
            return
        self._last_gesture_time = now
        await self._send({
            "type": "character_action",
            "action_type": "gesture",
            "value": gesture,
        })
```

### 2-D. 文脈ジェスチャー選択ロジック

AI transcript を軽量解析し，適切なジェスチャーを選択:

| テキストパターン | ジェスチャー |
|----------------|------------|
| "I think", "Let me think", "Well..." | thinking_pose |
| "Great!", "Excellent!", "Good job!" | thumbs_up / celebration |
| "I don't know", "I'm not sure" | shrug |
| 疑問文（"?"含む） | lean_forward |
| 長文説明（50語以上） | explain → open_palms 交互 |
| 挨拶系（"Hello", "Hi", "Goodbye"） | wave |

### 2-E. REALTIME_TOOLS 更新 (`tools.py`)

`play_gesture` の enum を拡張（AI function call経由での発火も維持）:

```python
"enum": ["nod", "wave", "thumbs_up", "explain", "listen",
         "shrug", "thinking_pose", "open_palms", "head_shake",
         "lean_forward", "celebration", "point", "idle_rest"],
```

### 修正ファイル
- `frontend/js/character.js` (2-A, 2-B: ジェスチャー定義+待機ポーズ)
- `src/english_skill_tester/api/websocket.py` (2-C, 2-D: GestureController)
- `src/english_skill_tester/realtime/tools.py` (2-E: enum拡張)
- `src/english_skill_tester/conversation/prompts.py` (ジェスチャー名更新)

### テスト方法
1. セッション開始で wave ジェスチャーが再生されること
2. ユーザ発話後に nod が再生されること
3. AI 長文応答中に explain 系ジェスチャーが再生されること
4. ジェスチャー間隔が 3秒以上あること（連発しない）
5. 全13種のジェスチャーが `playGesture()` で正常動作すること

---

## Phase 3: VRMモデル動的切り替え

### 目的
UIからVRMファイルをアップロードし，ランタイムでアバターを切り替え可能にする。

### 3-A. VRM アンロード/ロード関数 (`character.js`)

```javascript
// Public API に追加
async function loadModel(source) {
    // source: '/models/avatar.vrm' or blob URL
    const wasAnimating = initialized;
    initialized = false; // Pause animation loop

    // Unload current
    if (vrm) {
        activeGesture = null;
        gestureProgress = 0;
        gestureOriginalRotations = {};
        currentAudioLevel = 0;
        targetAudioLevel = 0;

        scene.remove(vrm.scene);
        vrm.scene.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
                mats.forEach(mat => {
                    if (mat.map) mat.map.dispose();
                    mat.dispose();
                });
            }
        });
        vrm = null;
    }

    // Load new
    const loader = new GLTFLoader();
    const { VRMLoaderPlugin } = await import('@pixiv/three-vrm');
    loader.register((parser) => new VRMLoaderPlugin(parser));

    return new Promise((resolve, reject) => {
        loader.load(source,
            (gltf) => {
                vrm = gltf.userData.vrm;
                if (vrm) {
                    scene.add(vrm.scene);
                    vrm.scene.rotation.y = Math.PI;
                    disableExpressionOverrides(); // Phase 1 の修正を新モデルにも適用
                    logDiagnostics(); // ボーン・expression 診断
                    initialized = true;
                    if (!wasAnimating) animate(); // 初回のみ animate 開始
                    resolve(vrm);
                } else {
                    reject(new Error('VRM data not found in file'));
                }
            },
            null,
            (error) => reject(error)
        );
    });
}
```

### 3-B. UI追加 (`index.html`)

```html
<!-- character-container 内に追加 -->
<div id="model-controls">
    <button id="btn-change-model" class="btn btn-small" title="VRMモデルを変更">
        🔄 モデル変更
    </button>
    <input type="file" id="vrm-upload" accept=".vrm" hidden>
    <span id="model-name" class="model-name-label">default</span>
</div>
```

### 3-C. イベントハンドリング (`app.js`)

```javascript
// モデル切り替え
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
```

### 3-D. CharacterController API 拡張 (`character.js`)

```javascript
window.CharacterController = {
    init: initCharacter,
    setExpression,
    playGesture,
    setAudioLevel,
    setAiSpeaking,
    loadModel,       // 追加
};
```

### 修正ファイル
- `frontend/js/character.js` (3-A, 3-D)
- `frontend/index.html` (3-B)
- `frontend/js/app.js` (3-C)
- `frontend/css/styles.css` (model-controls スタイル)

### テスト方法
1. デフォルト avatar.vrm が正常に表示されること
2. 別の VRM ファイルをアップロードし，モデルが切り替わること
3. 切り替え後にリップシンクが動作すること
4. 切り替え後にジェスチャーが動作すること（ボーン欠損時はスキップ）
5. 切り替え後に表情変化が動作すること
6. 不正ファイルアップロード時にエラー表示 + デフォルトモデル復帰
7. セッション中のモデル切り替えが安全に行えること

---

## タスク分割案（足軽割り当て）

| タスクID | Phase | 足軽 | 内容 | 依存 |
|----------|-------|------|------|------|
| subtask_002a | 1 | 足軽A | リップシンク修正 (1-A, 1-B, 1-C) | — |
| subtask_002b | 2 | 足軽B | 新ジェスチャー8種実装 (2-A, 2-B) | 002a |
| subtask_002c | 2 | 足軽C | ルールベースtrigger + 文脈選択 (2-C, 2-D, 2-E) | 002a |
| subtask_002d | 3 | 足軽D | VRMモデル切り替え (3-A〜3-D) | 002a |
| subtask_002e | — | 足軽E | ボーン診断ログ + 統合テスト | 002b,002c,002d |

**並列化**: 002a 完了後，002b / 002c / 002d は並列実行可能。

### 殿の厳命（全タスク共通）
- シェル: zsh前提
- Python: uv run, uv sync, uv add のみ使用（pip禁止）
- git commit は Phase 完了時に一括

---

## リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| VRMモデルごとにボーン構造が異なる | ジェスチャーが一部動かない | ボーン診断 + missing bone 時の fallback（ジェスチャースキップ） |
| expression 名がモデルごとに異なる | 表情変化が効かない | ロード時に利用可能な expression をログ出力 + カスタムマッピング |
| ルールベースtrigger が不自然 | 会話体験の低下 | min_interval (3s)，ランダム選択，文脈解析の段階的改善 |
| GestureController がイベントを大量発火 | ジェスチャー過多 | 間隔制限 + キュー制御（同時1ジェスチャーのみ） |
| VRM 切り替え時のメモリリーク | 長時間使用でパフォーマンス低下 | dispose() 確実実行 + Chrome DevTools で確認 |
