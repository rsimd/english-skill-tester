# English Skill Tester

OpenAI Realtime APIと3Dキャラクターインターフェースを使ったリアルタイム英会話スキル評価システム。

## 動作環境

- **Python**: 3.12以降
- **パッケージマネージャー**: uv (https://github.com/astral-sh/uv)
- **OS**: macOS、Linux、またはWindows上のWSL2
- **Node.js**: 不要（フロントエンドはHTML/CSS/JSのみ使用）
- **OpenAI APIキー**: Realtime APIへのアクセスに必要

## アーキテクチャ

```
[マイク] → sounddevice → Pythonバックエンド → OpenAI Realtime API (WebSocket)
[スピーカー] ← sounddevice ← Pythonバックエンド ← OpenAI Realtime API

Pythonバックエンド → FastAPI WebSocket → ブラウザ（3Dキャラクター + スコア表示 + UI）
```

- **音声I/O**: sounddevice経由でPython側がマイク・スピーカーを制御
- **Realtime API**: Python → OpenAI WebSocketで音声ストリーミング
- **フロントエンド**: FastAPIが静的ファイルを配信、WebSocketでリアルタイム更新
- **評価**: ルールベース（継続的）＋LLM（定期的）のハイブリッドスコアリング

## セットアップ

### 1. リポジトリのクローン
```bash
git clone https://github.com/rsimd/english-skill-tester.git
cd english-skill-tester
```

### 2. Python依存パッケージのインストール
```bash
uv sync
```

### 3. 環境変数の設定
```bash
cp .env.example .env
# .envを編集してOPENAI_API_KEYを追加する
```

### 4. （任意）VRMモデルの追加
VRMアバターファイルを `frontend/models/avatar.vrm` に配置する
（デフォルトモデルが同梱されています）

### 5. アプリケーションの起動
```bash
uv run python -m english_skill_tester.main
```

その後、ブラウザで `http://localhost:8000` を開く。

## 使い方

```bash
# サーバーを起動
uv run python -m english_skill_tester.main

# ブラウザで開く
open http://localhost:8000
```

1. **「会話開始」**をクリックしてセッションを開始
2. マイクに向かって話しかける ― AIがスピーカーから応答する
3. 右パネルでスコアがリアルタイムに更新されるのを確認
4. **「停止」**をクリックしてセッションを終了し、詳細なフィードバックを受け取る
5. **「レビュー」**ページで過去のセッションのトランスクリプトを確認

## スコアリング

ルールベースの言語分析と定期的なLLM評価を組み合わせたハイブリッド評価:

| 評価項目 | 重み | 評価方法 |
|----------|------|----------|
| 語彙力 | 20% | TTR、単語頻度、多様性 |
| 文法 | 25% | エラー検出、複雑さ |
| 流暢さ | 20% | フィラー比率、WPM、文の長さ |
| 理解力 | 15% | LLM評価 |
| 一貫性 | 15% | LLM評価 |
| 発音 | 5% | トランスクリプトのアーティファクト分析 |

スコアはTOEIC（10〜990）およびIELTS（1〜9）の推定値にマッピングされます。

## アダプティブ会話

AIはリアルタイムのスコアに基づいて会話スタイルを調整します:

- **初級** (0〜20): 簡単なYes/No質問と励ましの言葉
- **基礎** (20〜40): 簡単な開放型質問
- **中級** (40〜60): イディオムを交えた自然な会話
- **中上級** (60〜80): 抽象的な議論や仮定の話題
- **上級** (80〜100): ディベート、細かいニュアンスの分析

## 開発コマンド

### テスト実行
```bash
uv run pytest
```

### リント
```bash
uv run ruff check .
```

### フォーマット
```bash
uv run ruff format .
```

### 型チェック
```bash
uv run mypy src/
```

## 開発状況

### ✅ 完了 (cmd_001)
- [x] VRMモデルの表情制御
- [x] リップシンク実装（初期版）
- [x] 上半身ジェスチャー（5種類）
- [x] カメラ調整（上半身フォーカス）
- [x] 音声キャプチャのレイテンシ最適化
- [x] コード品質の改善
- [x] LLMによる文法チェック実装（gpt-4o-mini、フォールバック付き）
- [x] 非同期LLM評価
- [x] GitHubリポジトリのセットアップ

### 🔄 進行中 (cmd_002)
- [ ] リップシンクが途中で止まる問題の修正（overrideMouth問題）
- [ ] 新しいアメリカ式ジェスチャー8種追加（合計13種）
- [ ] ルールベースのジェスチャートリガー
- [ ] UIからのVRMモデル動的切り替え
- [ ] AIチューターペルソナの外部化（YAML）
- [ ] 統合YAMLコンフィグ

### 📋 計画中 / 提案 (cmd_003 レビュー)
- 48件の改善提案についてはdashboard.mdを参照（高優先度: 12件、中: 25件、低: 11件）
- 優先事項: P-SEC-002（パストラバーサル修正）、P-SEC-001（APIキー管理）

## プロジェクト構成

```
src/english_skill_tester/
├── main.py              # FastAPIエントリーポイント
├── config.py            # 設定（pydantic-settings）
├── audio/               # マイクキャプチャ、スピーカー再生、録音
├── realtime/            # OpenAI Realtime APIクライアント
├── assessment/          # ハイブリッドスコアリングエンジン
├── conversation/        # アダプティブプロンプトと戦略
├── analysis/            # セッション後フィードバック
├── api/                 # REST + WebSocketルート
└── models/              # Pydanticデータモデル
```
