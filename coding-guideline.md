# コーディング規約

本ドキュメントは、Document Reviewer プロジェクトのコードレビューにおける基準を定めたものです。

---

## 1. 全般

### 1.1 言語とバージョン

| 技術スタック | バージョン |
|-------------|-----------|
| Python | 3.12 以上 |
| TypeScript | 5.6 以上 |
| React | 18.x |
| Node.js | 18 以上 |

### 1.2 基本原則

- **KISS（Keep It Simple, Stupid）**: シンプルな実装を優先する
- **DRY（Don't Repeat Yourself）**: コードの重複を避ける
- **YAGNI（You Aren't Gonna Need It）**: 必要になるまで機能を追加しない
- セキュリティを最優先事項とする

### 1.3 コミットとバージョン管理

- コミットメッセージは変更内容を簡潔に記述する
- 1つのコミットは1つの論理的な変更に限定する
- 機密情報（API キー、認証情報など）をコミットしない

---

## 2. Python（バックエンド）

### 2.1 パッケージ管理

- **uv** を使用する（pip は禁止）
- インストール: `uv add <package>`
- 実行: `uv run <command>`
- アップグレード: `uv add --dev <package> --upgrade-package <package>`

### 2.2 コードフォーマット

- **Ruff** を使用してフォーマットとリント
- 行の最大長: **88 文字**
- インポート順序: 標準ライブラリ → サードパーティ → ローカル

```bash
# フォーマット
uv run --frozen ruff format .

# リントチェック
uv run --frozen ruff check .

# 自動修正
uv run --frozen ruff check . --fix
```

### 2.3 型ヒント

- すべての関数に型ヒントを付ける
- `Optional` よりも `| None` を使用する（Python 3.10+ スタイル）
- **Pyright** で型チェックを実行する

```python
# Good
def get_user(user_id: int) -> User | None:
    ...

# Bad
def get_user(user_id):
    ...
```

### 2.4 docstring

- 公開 API には Google 形式の docstring を必須とする
- 内部メソッドは必要に応じて記述

```python
def execute_review(self, request: ReviewRequest) -> ReviewResult:
    """
    ドキュメントレビューを実行する。

    Args:
        request: レビューリクエスト

    Returns:
        レビュー結果

    Raises:
        BedrockInvocationError: API 呼び出しエラー
    """
```

### 2.5 例外処理

- 具体的な例外クラスを使用する
- 例外は適切にログ出力する
- `except Exception` の使用は最小限に

```python
# Good
try:
    response = self.client.invoke_model(...)
except ClientError as e:
    logger.error(f"Bedrock API error: {e}")
    raise BedrockInvocationError(...) from e

# Bad
try:
    response = self.client.invoke_model(...)
except:
    pass
```

### 2.6 ロギング

- `logging` モジュールを使用する
- ログレベルを適切に設定する（DEBUG, INFO, WARNING, ERROR）
- ユーザーの機密情報をログに含めない

### 2.7 Pydantic モデル

- スキーマ定義には Pydantic v2 を使用する
- `Field` でバリデーションと説明を追加する
- Enum は `str` を継承させる

```python
class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ReviewComment(BaseModel):
    line_number: int | None = Field(
        default=None,
        description="対象行番号"
    )
    severity: Severity = Field(
        ...,
        description="重要度"
    )
```

### 2.8 FastAPI 固有

- ルーターはプレフィックスとタグを設定する
- レスポンスモデルを明示的に指定する
- エラーレスポンスを `responses` に定義する

```python
router = APIRouter(prefix="/api/review", tags=["review"])

@router.post(
    "/",
    response_model=ReviewResult,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)
async def execute_review(...) -> ReviewResult:
    ...
```

---

## 3. TypeScript / React（フロントエンド）

### 3.1 コードフォーマット

- **ESLint** を使用してリント
- インデント: スペース 2 つ
- セミコロン: なし（プロジェクト設定に従う）

```bash
npm run lint
```

### 3.2 型定義

- `any` の使用を禁止する
- インターフェースには JSDoc コメントを付ける
- `null` と `undefined` を明示的に区別する

```typescript
// Good
interface ReviewComment {
  line_number: number | null;
  section: string | null;
  comment: string;
  severity: "high" | "medium" | "low";
}

// Bad
interface ReviewComment {
  line_number: any;
  comment: any;
}
```

### 3.3 React コンポーネント

- 関数コンポーネントを使用する（クラスコンポーネント禁止）
- Props インターフェースを定義する
- `React.FC` は使用しない（明示的な戻り値型を推奨）

```typescript
// Good
interface DocumentUploadProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
}

export function DocumentUpload({
  onFileSelect,
  selectedFile,
}: DocumentUploadProps) {
  return <div>...</div>;
}

// Bad
export const DocumentUpload: React.FC<Props> = (props) => {
  ...
}
```

### 3.4 Hooks

- カスタムフックは `use` プレフィックスを付ける
- `useCallback` と `useMemo` は必要な場合のみ使用する
- 依存配列を正確に記述する

```typescript
// Good
const handleDrop = useCallback(
  (e: React.DragEvent) => {
    e.preventDefault();
    onFileSelect(e.dataTransfer.files[0]);
  },
  [onFileSelect]
);

// Bad（依存配列が不正確）
const handleDrop = useCallback((e: React.DragEvent) => {
  onFileSelect(e.dataTransfer.files[0]);
}, []);
```

### 3.5 状態管理

- ローカル状態には `useState` を使用する
- 複雑な状態には `useReducer` を検討する
- グローバル状態は必要最小限に

### 3.6 イベントハンドラ

- `handle` プレフィックスを使用する
- イベント型を明示的に指定する

```typescript
const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  const files = e.target.files;
  if (files && files.length > 0) {
    onFileSelect(files[0]);
  }
};
```

### 3.7 API 呼び出し

- エラーハンドリングを必ず実装する
- ローディング状態を管理する
- カスタムエラークラスを使用する

```typescript
export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}
```

---

## 4. 命名規則

### 4.1 Python

| 種類 | 規則 | 例 |
|------|------|-----|
| 変数・関数 | snake_case | `user_name`, `get_user()` |
| クラス | PascalCase | `ReviewService`, `BedrockClient` |
| 定数 | UPPER_SNAKE_CASE | `MAX_FILE_SIZE`, `DEFAULT_TIMEOUT` |
| プライベート | `_` プレフィックス | `_parse_response()` |

### 4.2 TypeScript

| 種類 | 規則 | 例 |
|------|------|-----|
| 変数・関数 | camelCase | `userName`, `getUser()` |
| 型・インターフェース | PascalCase | `ReviewResult`, `ApiError` |
| 定数 | UPPER_SNAKE_CASE | `API_BASE_URL` |
| コンポーネント | PascalCase | `DocumentUpload`, `ReviewResult` |
| イベントハンドラ | handle + 動詞 | `handleClick`, `handleFileChange` |

---

## 5. ディレクトリ構成

### 5.1 バックエンド

```
backend/
├── src/
│   ├── __init__.py
│   ├── main.py           # アプリケーションエントリポイント
│   ├── config.py         # 設定管理
│   ├── api/
│   │   └── routes/       # ルーター定義
│   ├── services/         # ビジネスロジック
│   ├── models/           # Pydantic モデル
│   └── schemas/          # リクエスト/レスポンススキーマ
├── tests/                # テストコード
└── pyproject.toml
```

### 5.2 フロントエンド

```
frontend/
├── src/
│   ├── main.tsx          # エントリポイント
│   ├── App.tsx           # メインアプリケーション
│   ├── components/       # React コンポーネント
│   │   └── ComponentName/
│   │       ├── ComponentName.tsx
│   │       └── index.ts
│   ├── hooks/            # カスタムフック
│   ├── services/         # API クライアント
│   ├── types/            # 型定義
│   └── __tests__/        # テストコード
├── e2e/                  # E2E テスト
└── package.json
```

### 5.3 コンポーネントの構成

- 1 コンポーネント = 1 ディレクトリ
- `index.ts` で再エクスポートする

```typescript
// components/DocumentUpload/index.ts
export { DocumentUpload } from "./DocumentUpload";
```

---

## 6. セキュリティ

### 6.1 入力検証

- すべてのユーザー入力を検証する
- ファイルアップロードは拡張子とサイズを制限する
- SQL インジェクション、XSS、コマンドインジェクションを防止する

### 6.2 認証情報

- 認証情報をハードコードしない
- 環境変数または設定ファイルを使用する
- `.env` ファイルをバージョン管理に含めない

### 6.3 エラーメッセージ

- 内部エラーの詳細をユーザーに公開しない
- スタックトレースを本番環境で表示しない

---

## 7. テスト

### 7.1 バックエンド

- **pytest** を使用する
- 非同期テストには **anyio** を使用する（asyncio ではない）
- カバレッジ: エッジケースとエラーケースを含める

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD="" uv run --frozen pytest
```

### 7.2 フロントエンド

- **Vitest** + React Testing Library を使用する
- E2E テストには **Playwright** を使用する

### 7.3 テスト命名規則

- テストファイル: `test_*.py`（Python）、`*.test.tsx`（TypeScript）
- テスト関数: `test_<機能>_<条件>_<期待結果>`

```python
def test_execute_review_with_valid_input_returns_result():
    ...

def test_execute_review_with_invalid_file_raises_error():
    ...
```

---

## 8. エラーハンドリング

### 8.1 HTTP ステータスコード

| コード | 用途 |
|--------|------|
| 200 | 正常完了 |
| 400 | リクエスト不正（バリデーションエラー） |
| 401 | 認証エラー |
| 403 | 権限エラー |
| 404 | リソース未検出 |
| 500 | サーバー内部エラー |

### 8.2 エラーレスポンス形式

```json
{
  "detail": "エラーの詳細メッセージ",
  "error_code": "INVALID_FILE_TYPE"
}
```

---

## 9. パフォーマンス

### 9.1 API 呼び出し

- タイムアウトを適切に設定する
- リトライロジックを実装する（指数バックオフ）
- 不要な API 呼び出しを避ける

### 9.2 フロントエンド

- 不要な再レンダリングを避ける
- 大きなリストには仮想スクロールを検討する
- 画像やアセットを最適化する

---

## 10. コードレビューチェックリスト

### 10.1 必須チェック項目

- [ ] 型ヒント/型定義が適切に記述されている
- [ ] エラーハンドリングが実装されている
- [ ] セキュリティ上の問題がない
- [ ] 命名規則に従っている
- [ ] 重複コードがない
- [ ] テストが追加/更新されている

### 10.2 警告レベルチェック項目

- [ ] パフォーマンスへの影響を考慮している
- [ ] ログ出力が適切
- [ ] docstring/コメントが必要な箇所に記述されている
- [ ] マジックナンバーが定数化されている

### 10.3 推奨チェック項目

- [ ] コードの可読性が高い
- [ ] 関数/メソッドが単一責任を持っている
- [ ] 将来の拡張性を考慮している
