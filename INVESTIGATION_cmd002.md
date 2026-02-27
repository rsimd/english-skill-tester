# INVESTIGATION: cmd_002 根本原因分析

**調査者**: 軍師 (gunshi)
**日時**: 2026-02-27
**対象**: VRM ジェスチャー・リップシンク・モデル切り替え

---

## 問題1: 手・腕ジェスチャーが動かない

### データフロー（正常時の想定）

```
AI (Realtime API) → function call: play_gesture("wave")
  → RealtimeClient._dispatch() → _handle_function_call()
    → registered lambda → function result 送信 → response_create
    → on_function_call handler (websocket.py:187)
      → _send_to_browser({type: "character_action", action_type: "gesture", value: "wave"})
        → Browser WS → app.js ws.on('character_action')
          → CharacterController.playGesture("wave")
            → saveOriginalRotations() → activeGesture = "wave"
              → animate() → updateGesture() → ボーン回転
```

### 根本原因: Realtime API がfunction callを発行しない

**確信度: 高**

コードパスは全て正しく実装されている。しかし，**OpenAI Realtime API は audio モードで server_vad 使用時，ツール呼び出しを極めて不安定にしか行わない**。

**証拠**:
1. セッション設定 (`events.py:26-38`):
   ```python
   "modalities": ["text", "audio"],
   "turn_detection": {"type": "server_vad", ...},
   "tools": REALTIME_TOOLS,
   "tool_choice": "auto",
   ```
2. `tool_choice: "auto"` は「AIに任せる」設定。音声ストリーミング中，AIは音声生成を優先し，function call をスキップする傾向が強い。
3. システムプロンプトに `Use the set_expression and play_gesture functions` と記述あるが，soft instruction であり強制力がない。

**補助的要因**:

| 要因 | 深刻度 | 詳細 |
|------|--------|------|
| VRMボーン未確認 | 中 | `getNormalizedBoneNode('rightUpperArm')` が null を返す可能性。ログ未出力で検証不能 |
| フロントエンド経路未到達 | 低 | `character_action` イベントがブラウザに届いていないか未検証。コンソールに "Gesture played:" が出るか要確認 |
| fallbackMode 誤検出 | 低 | VRM読み込み失敗時 `fallbackMode=true` だとCSS animationのみ。ただし3Dキャラが表示されているなら該当しない |

### 検証手順

```
1. ブラウザコンソールで "Gesture played:" を検索 → 出力あり=フロントエンド到達済み
2. Python ログで "function_call_executed" を検索 → 出力あり=Realtime API がfunction call実行
3. ブラウザコンソールで "VRM expressions available:" を確認 → ボーン名一覧確認
```

### 修正方針

**A. ルールベースジェスチャートリガー（推奨・最優先）**

AI function callに依存せず，バックエンドでイベント駆動のジェスチャー発火を実装:

| トリガー | ジェスチャー | 実装箇所 |
|----------|------------|----------|
| ユーザ発話終了 | nod | `on_user_transcript` |
| AI応答開始 | explain | `on_response_started` |
| AI応答2文以上 | explain / listen 交互 | `on_ai_transcript` |
| セッション開始 | wave | `start()` |
| 高スコア更新 | thumbs_up | `_score_update_loop` |
| 沈黙5秒以上 | listen | タイマー |

**B. ボーン診断ログ追加**

`character.js` のVRMロード後にボーン一覧をログ出力:

```javascript
// loadVRM() 内，vrm取得後
if (vrm.humanoid) {
    const boneNames = ['head', 'rightUpperArm', 'rightLowerArm',
                       'leftUpperArm', 'leftLowerArm', 'spine'];
    boneNames.forEach(name => {
        const bone = vrm.humanoid.getNormalizedBoneNode(name);
        console.log(`Bone [${name}]:`, bone ? 'found' : 'MISSING');
    });
}
```

**C. Realtime API ツール呼び出し強化（補助的）**

- プロンプトに「Every response MUST include at least one function call」のような強い指示を追加
- ただし音声モードでの効果は限定的

---

## 問題2: リップシンクが途中で停止する

### データフロー

```
Realtime API → response.audio.delta (音声チャンク)
  → websocket.py on_audio_delta
    → base64_to_pcm16 → np.abs(audio).mean() → level計算
    → _send_to_browser({type: "audio_level", level: 0.0-1.0})
      → Browser → CharacterController.setAudioLevel(level)
        → targetAudioLevel = level
          → animate() → updateLipSync()
            → vrm.expressionManager.setValue('aa', mouthOpen * 0.8)

Realtime API → response.created
  → _send_to_browser({type: "ai_speaking", speaking: true})
    → CharacterController.setAiSpeaking(true)
      → aiSpeaking = true

Realtime API → response.done
  → _send_to_browser({type: "ai_speaking", speaking: false})
    → CharacterController.setAiSpeaking(false)
      → aiSpeaking = false, targetAudioLevel = 0
```

### 根本原因: VRM Expression Override によるmouth shapes抑制

**確信度: 高**

VRM仕様では，プリセット表情（happy, angry, sad, surprised, relaxed）に **overrideMouth** フラグが設定されている場合がある。このフラグが有効な場合:

1. `setExpression("happy")` → `expressionManager.setValue('happy', 0.7)`
2. VRM内部で `happy` expression の `overrideMouth` が発動
3. 口形状関連の expression ('aa', 'oh', 'ee') が **自動的にブロック** される
4. `updateLipSync()` は毎フレーム 'aa', 'oh', 'ee' を設定し続けるが，override により反映されない
5. **結果: 口が動かなくなる**

**症状との完全一致**:
- 「最初は口が動くが」 → 初期 expression は 'neutral'（overrideMouth なし）
- 「喋り続けると途中で止まる」 → AI が `set_expression("happy")` 等を呼ぶタイミングで停止

**コード箇所** (`character.js:437-473`):
```javascript
function setExpression(expression) {
    // emotion expressions をリセット
    vrm.expressionManager.setValue('happy', 0);  // ← ここで解除
    // 新しい expression を設定
    vrm.expressionManager.setValue(preset, 0.7);  // ← overrideMouth 発動！
}
```

### 補助的要因

| 要因 | 深刻度 | 詳細 |
|------|--------|------|
| Response lifecycle gap | 中 | function call 時に response.done → aiSpeaking=false → 次の response.created まで数百ms のgap |
| audio_level 遅延 | 低 | WebSocket メッセージの遅延による一時的な level=0 |

### 修正方針

**A. Expression weight 制御（推奨）**

リップシンク活性時は expression weight を下げ，mouth override を防ぐ:

```javascript
function setExpression(expression) {
    // Reset
    ['happy', 'angry', 'sad', 'surprised', 'relaxed'].forEach(e =>
        vrm.expressionManager.setValue(e, 0));

    const preset = presetMap[expression];
    if (preset) {
        // リップシンク中は expression weight を制限
        const weight = aiSpeaking ? 0.3 : 0.7;
        vrm.expressionManager.setValue(preset, weight);
    }
}
```

**B. Lip sync → Expression 適用順序の制御**

`updateLipSync()` 内で mouth shapes を設定した **後に** `expressionManager.update()` を呼び，mouth shapes が最終値として残るようにする。

あるいは，VRM の `overrideMouth` を実行時に無効化:
```javascript
// expression の overrideMouth を無効化
if (vrm.expressionManager) {
    vrm.expressionManager.expressions.forEach(expr => {
        if (expr.overrideMouth) {
            expr.overrideMouth = 'none'; // override 解除
        }
    });
}
```

**C. aiSpeaking フラグの改善**

`response.done` 直後に aiSpeaking を false にせず，playback バッファが空になるまで待つ:

```python
async def on_response_done(event: dict) -> None:
    # 遅延して aiSpeaking を解除（バッファ再生完了待ち）
    await asyncio.sleep(0.5)
    if not self._ai_speaking:  # 次の response で true に戻っていなければ
        await self._send_to_browser({"type": "ai_speaking", "speaking": False})
        await self._send_to_browser({"type": "audio_level", "level": 0})
```

---

## 問題3: VRMモデル動的切り替え（新機能設計）

### 現在のVRMロード処理

```
initCharacter()
  → loadVRM()
    → GLTFLoader + VRMLoaderPlugin
    → loader.load('/models/avatar.vrm')
      → gltf.userData.vrm → vrm (module-level variable)
      → scene.add(vrm.scene)
      → vrm.scene.rotation.y = Math.PI
  → animate() 開始
```

**現在の制約**:
- モデルパス `/models/avatar.vrm` がハードコード
- VRM は module-level 変数 `vrm` に格納（1体のみ）
- ロード後の再ロード処理なし
- GPU リソース解放処理なし

### 設計方針

**3段階アプローチ**:

#### Step 1: VRM アンロード関数

```javascript
function unloadCurrentVRM() {
    if (!vrm) return;

    // アニメーション状態リセット
    activeGesture = null;
    gestureProgress = 0;
    gestureOriginalRotations = {};
    currentAudioLevel = 0;
    targetAudioLevel = 0;
    aiSpeaking = false;

    // シーンから除去
    scene.remove(vrm.scene);

    // GPU リソース解放
    vrm.scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
            const materials = Array.isArray(obj.material)
                ? obj.material : [obj.material];
            materials.forEach(mat => {
                Object.values(mat).forEach(val => {
                    if (val && typeof val.dispose === 'function') val.dispose();
                });
                mat.dispose();
            });
        }
    });

    vrm = null;
}
```

#### Step 2: 新VRMロード関数（URL/Blob対応）

```javascript
async function loadVRMFromSource(source) {
    // source: URL string or Blob URL
    unloadCurrentVRM();

    const loader = new GLTFLoader();
    const { VRMLoaderPlugin } = await import('@pixiv/three-vrm');
    loader.register((parser) => new VRMLoaderPlugin(parser));

    return new Promise((resolve, reject) => {
        loader.load(source, (gltf) => {
            vrm = gltf.userData.vrm;
            if (vrm) {
                scene.add(vrm.scene);
                vrm.scene.rotation.y = Math.PI;
                logBoneAvailability();  // 診断ログ
                logExpressionAvailability();
            }
            resolve(vrm);
        }, null, reject);
    });
}
```

#### Step 3: UI統合

```html
<!-- index.html に追加 -->
<div id="model-controls">
    <input type="file" id="vrm-upload" accept=".vrm" style="display:none">
    <button id="btn-change-model" class="btn btn-secondary">モデル変更</button>
    <span id="model-name">avatar.vrm</span>
</div>
```

```javascript
// app.js に追加
document.getElementById('btn-change-model').addEventListener('click', () => {
    document.getElementById('vrm-upload').click();
});

document.getElementById('vrm-upload').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file || !file.name.endsWith('.vrm')) return;

    const blobUrl = URL.createObjectURL(file);
    try {
        await CharacterController.loadModel(blobUrl);
        document.getElementById('model-name').textContent = file.name;
    } catch (err) {
        console.error('Failed to load VRM:', err);
        alert('VRMモデルの読み込みに失敗しました');
    } finally {
        URL.revokeObjectURL(blobUrl);
    }
});
```

### リスク

| リスク | 対策 |
|--------|------|
| 新モデルにジェスチャー用ボーンがない | ロード後にボーン診断，欠損時は該当ジェスチャーを無効化 |
| 新モデルのexpression名が異なる | ロード後にexpression一覧を取得し，利用可能なexpressionにマッピング |
| メモリリーク | 旧モデルのGPUリソースを確実に `dispose()` |
| 切り替え中にリップシンク/ジェスチャーが破綻 | ロード完了まで animate() を一時停止 |
| ファイルサイズが大きい（>50MB） | プログレスバー表示，サイズ上限チェック |

---

## 優先順位まとめ

| # | 問題 | 根本原因 | 修正難度 | 優先度 |
|---|------|---------|---------|--------|
| 1 | ジェスチャー未動作 | Realtime API がfunction callしない | 中（ルールベースtrigger実装） | **最高** |
| 2 | リップシンク停止 | VRM expression overrideMouth | 低（weight調整 or override解除） | **高** |
| 3 | VRMモデル切り替え | 新機能 | 中（unload/load/UI） | **中** |

問題1と2は相互関連: 問題1の修正（ルールベースtrigger）で expression が頻繁に変わると，問題2（overrideMouth）がより顕著になる。**問題2を先に修正すべき**。
