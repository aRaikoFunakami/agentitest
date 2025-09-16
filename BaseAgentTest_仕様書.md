# BaseAgentTest クラス仕様書

## 概要

`BaseAgentTest` は、Browser Use エージェントを用いたWebブラウザ自動化テストの共通基盤クラスです。テストの簡素化、共通処理の統一、Allureレポートとの統合を提供し、エージェントベースのテストを効率的に実装できます。

## 目的

- Browser Useエージェントを活用したWebアプリケーションのE2Eテストの標準化
- テストコードの重複排除とメンテナンス性の向上
- Allureテストレポートとの詳細な統合による可視性の提供
- AIエージェントの思考プロセスとブラウザ操作の詳細記録

## クラス構造

### 基本情報

```python
class BaseAgentTest:
    """Base class for agent-based tests to reduce boilerplate."""
    
    BASE_URL = "https://discuss.google.dev/"
```

### 属性

| 属性名 | 型 | 説明 | デフォルト値 |
|--------|----|----|------------|
| `BASE_URL` | `str` | テスト対象の基本URL | `"https://discuss.google.dev/"` |

## 主要メソッド

### validate_task メソッド

エージェントタスクの実行と検証を行う中核メソッドです。

#### シグネチャ

```python
async def validate_task(
    self,
    llm: ChatOpenAI,
    browser_session: BrowserSession,
    task_instruction: str,
    expected_substring: Optional[str] = None,
    ignore_case: bool = False,
) -> str:
```

#### パラメータ

| パラメータ名 | 型 | 必須 | 説明 |
|-------------|----|----|------|
| `llm` | `ChatOpenAI` | ✓ | 使用する言語モデルインスタンス |
| `browser_session` | `BrowserSession` | ✓ | ブラウザセッションインスタンス |
| `task_instruction` | `str` | ✓ | エージェントに実行させる具体的な指示（URLアクセス部分は除く） |
| `expected_substring` | `Optional[str]` | - | 結果に含まれることを期待する文字列 |
| `ignore_case` | `bool` | - | 文字列比較時の大文字小文字無視フラグ |

#### 戻り値

- `str`: エージェントが返した最終結果テキスト

#### 処理フロー

1. **タスク構築**: `BASE_URL` を前置した完全なタスク指示を生成
2. **エージェント実行**: `run_agent_task` 関数を呼び出してタスクを実行
3. **結果検証**:
   - 結果がNoneでないことを確認
   - `expected_substring` が指定されている場合、その文字列が結果に含まれることを検証
4. **結果返却**: 検証済みの結果テキストを返却

#### 例外

- `AssertionError`: 結果がNoneまたは期待する文字列が見つからない場合

### expected_substring による テスト成功・失敗判定

`expected_substring`パラメータは、BaseAgentTestの中核となるテスト判定メカニズムです。このパラメータにより、エージェントの実行結果が期待通りかを自動的に検証します。

#### 判定の仕組み

BaseAgentTestは以下の2段階構造でテストの成功/失敗を判定します：

1. **指示（task）**: エージェントに条件を満たした場合に特定の文字列を返すよう明示的に指示
2. **検証（expected_substring）**: その特定の文字列が実際の結果に含まれているかをチェック

#### 判定ロジックの実装

```python
if expected_substring:
    result_to_check = result_text.lower() if ignore_case else result_text
    substring_to_check = (
        expected_substring.lower() if ignore_case else expected_substring
    )
    assert (
        substring_to_check in result_to_check
    ), f"Assertion failed: Expected '{expected_substring}' not found in agent result: '{result_text}'"
```

#### テスト成功・失敗の判定基準

| 条件 | 結果 | 説明 |
|------|------|------|
| `expected_substring` がNoneまたは空 | **常に成功** | 文字列チェックをスキップ |
| `expected_substring` が結果に含まれる | **✅ テスト成功** | エージェントが期待通りの判断を行った |
| `expected_substring` が結果に含まれない | **❌ テスト失敗** | エージェントが期待と異なる判断を行った |
| エージェントの結果がNone | **❌ テスト失敗** | エージェント実行エラー |

#### 実用的な使用例

##### 例1: 要素の存在確認

```python
# テストクラスで定数定義
EXPECTED_STATS_RESULT = "all_stats_visible"

# タスク指示（条件分岐を含む明確な指示）
task = f"confirm that the stats for 'Members', 'Online', and 'Solutions' are visible on the page. Return '{self.EXPECTED_STATS_RESULT}' if they are."

# 検証実行
await self.validate_task(llm, browser_session, task, self.EXPECTED_STATS_RESULT, ignore_case=True)
```

**判定結果例**:

- ✅ 成功: `"I found all the stats visible on the page. all_stats_visible"`
- ❌ 失敗: `"I could not locate the Members stat on the page."`

##### 例2: 検索結果の状態確認

```python
EXPECTED_NO_RESULTS = "no_results_found"

task = f"find the search bar, type '{term}', press enter, and confirm that a 'no results' message is displayed. Return '{self.EXPECTED_NO_RESULTS}' if it is."

await self.validate_task(llm, browser_session, task, self.EXPECTED_NO_RESULTS, ignore_case=True)
```

**判定結果例**:

- ✅ 成功: `"Search completed. No results were found for the term. no_results_found"`
- ❌ 失敗: `"Search completed. Found 5 results for the term."`

##### 例3: ナビゲーション後のURL確認

```python
expected_url_part = f"search?q={quote(term)}"
task = f"find the search bar, type '{term}', submit the search, and return the final URL."

await self.validate_task(llm, browser_session, task, expected_url_part)
```

**判定結果例**:

- ✅ 成功: `"https://discuss.google.dev/search?q=BigQuery"`
- ❌ 失敗: `"https://discuss.google.dev/"`

#### ignore_case パラメータとの連携

```python
# 大文字小文字を無視する場合
await self.validate_task(llm, browser_session, task, "SUCCESS", ignore_case=True)
# "SUCCESS", "Success", "success" などすべてマッチ

# 厳密にチェックする場合（デフォルト）
await self.validate_task(llm, browser_session, task, "SUCCESS")
# "SUCCESS" のみマッチ
```

#### エラーメッセージ例

```text
AssertionError: Assertion failed: Expected 'all_stats_visible' not found in agent result: 'The page does not contain visible stats for Members, Online, and Solutions.'
```

#### 高度な使用パターン

##### パターン1: 条件分岐型の指示

```python
task = """
ログインフォームに以下の情報を入力してください：
- ユーザー名: testuser  
- パスワード: wrongpassword

ログインが成功した場合は 'LOGIN_SUCCESS' を、
失敗した場合は 'LOGIN_FAILED' を返してください。
"""

# 意図的に失敗を期待するテスト
await self.validate_task(llm, browser_session, task, "LOGIN_FAILED")
```

##### パターン2: 複数条件の確認

```python
task = """
以下の要素がすべてページに存在するか確認してください：
1. ヘッダーナビゲーション
2. フッター  
3. 検索バー

すべて存在する場合は 'ALL_ELEMENTS_PRESENT' を、
一つでも欠けている場合は 'MISSING_ELEMENTS' を返してください。
"""

await self.validate_task(llm, browser_session, task, "ALL_ELEMENTS_PRESENT")
```

##### パターン3: 数値条件の検証

```python
task = """
商品一覧ページで商品数を数えてください。
商品が10個以上ある場合は 'SUFFICIENT_PRODUCTS' を、
10個未満の場合は 'INSUFFICIENT_PRODUCTS' を返してください。
"""

await self.validate_task(llm, browser_session, task, "SUFFICIENT_PRODUCTS")
```

#### expected_substring のベストプラクティス

1. **一意で明確な文字列を選択**: 偶然マッチしない、テスト固有の文字列を使用
2. **タスク指示との整合性**: エージェントに返すべき文字列を明確に伝達
3. **条件の明確化**: どの条件で成功/失敗文字列を返すかを詳細に指示
4. **大文字小文字の考慮**: 必要に応じて`ignore_case=True`を活用

#### expected_substring を使用しない場合

```python
# expected_substring を指定しない場合は文字列チェックをスキップ
result = await self.validate_task(llm, browser_session, task)
# 独自の検証ロジックを実装
assert "期待する内容" in result
```

この仕組みにより、エージェントの「理解力」「判断力」「実行力」を総合的にテストでき、テスト結果の信頼性と自動化を実現しています。

## Allure統合機能

BaseAgentTestはAllureテストレポートと密接に統合されており、以下の情報を自動的に記録・添付します。

### 記録される情報一覧

#### 1. 環境情報（環境プロパティ）

テスト実行時の環境情報が `environment.properties` として記録されます。

| プロパティ名 | 説明 | 例 |
|------------|------|-----|
| `operating_system` | OS名とバージョン | `Darwin 24.6.0` |
| `python_version` | Pythonバージョン | `3.13.7` |
| `browser_use_version` | Browser Useライブラリバージョン | `0.4.0` |
| `playwright_version` | Playwrightバージョン | `1.55.0` |
| `browser_type` | 使用ブラウザタイプ | `chromium` |
| `browser_version` | ブラウザバージョン | `140.0.7339.16` |
| `headless_mode` | ヘッドレスモード設定 | `True` |
| `llm_model` | 使用LLMモデル | `gpt-4o` |

#### 2. ステップ別詳細情報

各エージェントのアクションごとに以下の情報が記録されます：

| アタッチメント名 | 型 | 説明 | ファイル形式 |
|-----------------|----|----|------------|
| **Agent Thoughts** | `TEXT` | AIエージェントの思考内容・判断プロセス | `.txt` |
| **URL** | `URI_LIST` | アクション実行時のページURL | `.uri` |
| **Step Duration** | `TEXT` | 各ステップの実行時間 | `.txt` |
| **Screenshot after Action** | `PNG` | アクション実行後のスクリーンショット | `.png` |

#### 3. テスト全体情報

| アタッチメント名 | 型 | 説明 | ファイル形式 |
|-----------------|----|----|------------|
| **Agent Final Output** | `TEXT` | エージェントの最終実行結果 | `.txt` |
| **log** | `TEXT` | テスト実行ログ | `.txt` |

### 情報収集・記録タイミング

#### 1. セッション開始時（environment_reporter フィクスチャ）

- **タイミング**: テストセッション開始時（`scope="session", autouse=True`）
- **処理**: `environment.properties` ファイルを生成
- **場所**: `--alluredir` で指定されたディレクトリ

#### 2. 各エージェントステップ終了時（record_step フック）

- **タイミング**: エージェントが各アクションを完了した直後
- **処理**: `on_step_end=record_step` コールバックで実行
- **記録内容**:
  - アクション名とパラメータでステップタイトルを構成
  - エージェントの思考内容を取得・添付
  - 現在のURLを記録
  - ステップ実行時間を記録
  - スクリーンショットを撮影・添付（base64デコード処理）

#### 3. テスト完了時（run_agent_task 関数）

- **タイミング**: エージェントタスク実行完了時
- **処理**: `@allure.step` デコレータ内で実行
- **記録内容**:
  - エージェントの最終結果をテキストとして添付

### 実装詳細

#### record_step フック関数の動作

```python
async def record_step(agent: Agent):
    """Hook function that captures and records agent activity at each step."""
    history = agent.state.history
    if not history:
        return

    # アクション情報の抽出
    last_action = history.model_actions()[-1] if history.model_actions() else {}
    action_name = next(iter(last_action)) if last_action else "No action"
    action_params = last_action.get(action_name, {})

    # ステップタイトルの構成
    step_title = f"Action: {action_name}"
    if action_params:
        param_str = ", ".join(f"{k}={v}" for k, v in action_params.items())
        step_title += f"({param_str})"

    with allure.step(step_title):
        # 各種情報の添付処理...
```

#### スクリーンショット処理

- Browser Sessionから base64形式でスクリーンショットを取得
- base64デコードしてバイナリデータに変換
- PNGフォーマットでAllureに添付

## 使用例

### 基本的な使用方法

```python
import allure
import pytest
from conftest import BaseAgentTest

@allure.feature("ウェブサイト機能テスト")
class TestWebsiteFunctionality(BaseAgentTest):
    """ウェブサイトの機能テストクラス"""

    @allure.story("ナビゲーションテスト")
    @allure.title("メインナビゲーションのテスト")
    @pytest.mark.asyncio
    async def test_main_navigation(self, llm, browser_session):
        """メインナビゲーションのクリックテスト"""
        task = "メニューから'About'リンクをクリックして、ページタイトルを取得する"
        result = await self.validate_task(
            llm, 
            browser_session, 
            task, 
            expected_substring="About"
        )
        # resultを使った追加検証...
```

### パラメータ化テストの例

```python
@pytest.mark.parametrize(
    "link_text, expected_path",
    [
        ("Google Cloud", "google-cloud"),
        ("Looker", "looker"),
        ("AppSheet", "appsheet"),
    ],
)
async def test_navigation_links(self, llm, browser_session, link_text, expected_path):
    """ナビゲーションリンクのテスト"""
    task = f"'{link_text}'リンクをクリックして最終URLを返す"
    result_url = await self.validate_task(
        llm, browser_session, task, expected_path
    )
    assert expected_path in result_url
```

### 検索機能テストの例

```python
@allure.story("検索機能")
@pytest.mark.asyncio
async def test_search_functionality(self, llm, browser_session):
    """検索機能のテスト"""
    search_term = "BigQuery"
    task = f"検索バーに'{search_term}'を入力して検索を実行し、結果ページを確認する"
    
    await self.validate_task(
        llm, 
        browser_session, 
        task, 
        expected_substring="search results",
        ignore_case=True
    )
```

## 依存関係とセットアップ

### 必要なフィクスチャ

BaseAgentTestを使用するテストでは以下のフィクスチャが必要です：

1. **llm** (`ChatOpenAI`): セッションスコープのLLMインスタンス
2. **browser_session** (`BrowserSession`): 関数スコープのブラウザセッション

### pytest設定

```ini
[pytest]
addopts = -s --alluredir=allure-results
log_cli = true
log_cli_level = INFO
log_cli_format = %(asctime)s - %(levelname)s - %(message)s
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

### 必要なライブラリ

```python
browser_use[all]==0.4.0
python_dotenv==1.1.1
allure_pytest==2.14.3
pytest_asyncio==1.0.0
```

## エラーハンドリング

### 一般的なエラーと対処法

1. **AssertionError: Agent did not return a final result.**
   - 原因: エージェントがタスクを完了できない
   - 対処: タスク指示の明確化、タイムアウト設定の見直し

2. **AssertionError: Expected 'xxx' not found in agent result**
   - 原因: 期待する文字列が結果に含まれない
   - 対処: `ignore_case=True` の使用、期待文字列の見直し

3. **TypeError: a bytes-like object is required, not 'NoneType'**
   - 原因: エージェントの最終結果がNone
   - 対処: エージェントの実行ログを確認、タスク指示の見直し

## ベストプラクティス

### 1. タスク指示の記述

- 具体的で明確な指示を記述
- 期待する結果の形式を明示
- 複雑なタスクは段階的に分割

### 2. Allureアノテーションの活用

```python
@allure.feature("機能名")
@allure.story("ストーリー名")
@allure.title("テストタイトル")
@pytest.mark.asyncio
async def test_method(self, llm, browser_session):
    # テスト実装
```

### 3. エラーレポートの活用

- Allureレポートのスクリーンショットで問題箇所を特定
- エージェントの思考ログで判断プロセスを確認
- ステップ実行時間でパフォーマンス問題を検出

## カスタマイズ

### BASE_URLの変更

```python
class CustomBaseAgentTest(BaseAgentTest):
    BASE_URL = "https://example.com/"
```

### 独自の検証ロジック追加

```python
class ExtendedBaseAgentTest(BaseAgentTest):
    
    async def validate_task_with_screenshot(self, llm, browser_session, task_instruction):
        """スクリーンショット付きの検証"""
        result = await self.validate_task(llm, browser_session, task_instruction)
        
        # 追加のスクリーンショット撮影
        screenshot = await browser_session.take_screenshot()
        allure.attach(
            base64.b64decode(screenshot),
            name="Final State Screenshot",
            attachment_type=allure.attachment_type.PNG
        )
        
        return result
```

## 技術的実装詳細

### フィクスチャの実装

```python
@pytest.fixture(scope="session")
def llm() -> ChatOpenAI:
    """Session-scoped fixture to initialize the language model."""
    return ChatOpenAI(model="gpt-4o")

@pytest.fixture(scope="session")
def browser_profile() -> BrowserProfile:
    """Session-scoped fixture for browser profile configuration."""
    headless_mode = os.getenv("HEADLESS", "True").lower() in ("true", "1", "t")
    return BrowserProfile(headless=headless_mode)

@pytest.fixture(scope="function")
async def browser_session(
    browser_profile: BrowserProfile,
) -> AsyncGenerator[BrowserSession, None]:
    """Function-scoped fixture to manage the browser session's lifecycle."""
    session = BrowserSession(browser_profile=browser_profile)
    yield session
    await session.close()
```

### run_agent_task関数の実装

```python
@allure.step("Running browser agent with task: {task_description}")
async def run_agent_task(
    task_description: str,
    llm: ChatOpenAI,
    browser_session: BrowserSession,
) -> Optional[str]:
    """Initializes and runs the browser agent for a given task using an active browser session."""
    logging.info(f"Running task: {task_description}")

    agent = Agent(
        task=task_description,
        llm=llm,
        browser_session=browser_session,
        name=f"Agent for '{task_description[:50]}...'",
    )

    result = await agent.run(on_step_end=record_step)

    final_text = result.final_result()
    allure.attach(
        final_text,
        name="Agent Final Output",
        attachment_type=allure.attachment_type.TEXT,
    )

    logging.info("Task finished.")
    return final_text
```

## まとめ

BaseAgentTestクラスは、Browser Useエージェントを活用したE2Eテストの実装を大幅に簡素化し、詳細なAllureレポート統合を提供します。このクラスを継承することで、AIエージェントの思考プロセス、ブラウザ操作の詳細、実行環境情報を含む包括的なテストレポートを自動生成できます。

テスト開発者は、複雑なセットアップや詳細な記録処理を気にすることなく、テストロジックに集中でき、高品質で可視性の高いWebアプリケーションテストを効率的に作成できます。
