"""
Android Base Agent Test
Pythonの単体テストからLLMエージェントを使ってAndroidアプリの自動操作テストを実行
"""

import asyncio
import time
import os
import base64
from typing import Dict, List, Optional
from dataclasses import dataclass

import allure
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient


@dataclass
class AgentState:
    """エージェントの状態管理"""
    device_id: Optional[str] = None
    current_app: Optional[str] = None
    operation_history: List[str] = None
    
    def __post_init__(self):
        if self.operation_history is None:
            self.operation_history = []


class AndroidBaseAgentTest:
    """Android アプリケーション自動化テスト用の基底クラス
    
    Mobile-MCPを使用してAndroidデバイス上でアプリケーションテストを実行する。
    既存のBaseAgentTestクラスのAndroid版相当機能を提供。
    """
    
    # デフォルト設定
    DEFAULT_APP_BUNDLE_ID = "com.android.chrome"
    APPIUM_SERVER_URL = "http://localhost:4723"
    MCP_SERVER_TIMEOUT = 30.0
    
    # クラス変数でデバイス情報をキャッシュ（重複検索防止）
    _device_cache = {
        'device_id': None,
        'timestamp': None,
        'cache_duration': 300  # 5分間キャッシュ
    }
    
    def __init__(self):
        """AndroidBaseAgentTestインスタンスの初期化"""
        self.mcp_client: Optional[MultiServerMCPClient] = None
        self.agent = None
        self.llm = ChatOpenAI(
            model="gpt-4.1",
            temperature=0,
            timeout=60,
            max_retries=2,
            output_version="responses/v1",
        )
        self._current_device_id: Optional[str] = None
        self._current_app_bundle_id: Optional[str] = None
        
        # エージェント状態管理を追加
        self.agent_state = AgentState()
        self.conversation_history: List[Dict[str, str]] = []
    
    async def setup_mobile_agent(self, device_id: Optional[str] = None):
        """モバイルエージェントの初期化とセットアップ
        
        Args:
            device_id: 接続対象のAndroidデバイスID (省略時は自動検出)
        """
        await self._initialize_mcp_client()
        
        # デバイスIDをキャッシュから取得または検索
        if device_id:
            self._current_device_id = device_id
            self._device_cache['device_id'] = device_id
            self._device_cache['timestamp'] = time.time()
        else:
            self._current_device_id = await self._get_cached_device_id()
        
        await self._initialize_react_agent()
    
    async def _get_cached_device_id(self) -> str:
        """キャッシュされたデバイスIDを取得、必要に応じて更新"""
        current_time = time.time()
        
        # キャッシュが有効な場合はそれを使用
        if (self._device_cache['device_id'] and 
            self._device_cache['timestamp'] and
            current_time - self._device_cache['timestamp'] < self._device_cache['cache_duration']):
            return self._device_cache['device_id']
        
        # キャッシュが無効な場合のみデバイス検索を実行
        try:
            # MCPツールを取得して直接呼び出し
            mobile_tools = await self.mcp_client.get_tools()
            devices_tool = None
            
            # mobile_list_available_devicesツールを検索
            for tool in mobile_tools:
                if hasattr(tool, 'name') and tool.name == 'mobile_list_available_devices':
                    devices_tool = tool
                    break
            
            if not devices_tool:
                print("mobile_list_available_devices tool not found")
                return "emulator-5554"  # デフォルト値を返す
                
            devices_result = await devices_tool.ainvoke({})
            
            if devices_result and hasattr(devices_result, 'content'):
                content = devices_result.content
                if isinstance(content, list):
                    device_text = "\n".join([item.get("text", str(item)) for item in content if isinstance(item, dict)])
                else:
                    device_text = content
                
                # emulator-5554 を優先的に検索
                if "emulator-5554" in device_text:
                    device_id = "emulator-5554"
                elif "emulator-" in device_text:
                    import re
                    match = re.search(r'emulator-\d+', device_text)
                    device_id = match.group() if match else None
                else:
                    device_id = None
                
                if device_id:
                    # キャッシュを更新
                    self._device_cache['device_id'] = device_id
                    self._device_cache['timestamp'] = current_time
                    return device_id
                    
        except Exception as e:
            # エラー時はフォールバック値を使用
            allure.attach(f"Device search error: {str(e)}", name="Device Search Warning", attachment_type=allure.attachment_type.TEXT)
        
        # フォールバック：デフォルトエミュレータID
        fallback_device = "emulator-5554"
        self._device_cache['device_id'] = fallback_device
        self._device_cache['timestamp'] = current_time
        return fallback_device
    
    async def _initialize_mcp_client(self):
        """MCP クライアントの初期化"""
        self.mcp_client = MultiServerMCPClient({
            "mobile": {
                "transport": "stdio",
                "command": "/opt/homebrew/opt/node@20/bin/npx",
                "args": ["-y", "@mobilenext/mobile-mcp@latest"],
                "env": {
                    "APPIUM_SERVER": self.APPIUM_SERVER_URL,
                    "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
                    "PATH": os.environ.get("PATH", "")
                }
            }
        })
    
    async def _initialize_react_agent(self):
        """ReActエージェントの初期化"""
        if not self.mcp_client:
            raise RuntimeError("MCP client must be initialized first")
        
        mobile_tools = await self.mcp_client.get_tools()
        
        # LangGraphエージェントを作成（効率化設定）
        self.agent = create_react_agent(
            self.llm,
            mobile_tools,
            prompt=self._get_mobile_agent_prompt()
            # 注意: create_react_agent()はrecursion_limitやmax_iterationsを引数として受け取らない
            # これらの制限は実行時のconfigで指定する
        )
    
    def _get_mobile_agent_prompt(self) -> str:
        """モバイルエージェント用の効率化されたシステムプロンプト
        
        Returns:
            エージェントに与える最適化されたシステムプロンプト文字列
        """
        device_override = self._current_device_id or "emulator-5554"
        
        return f"""ANDROID AUTOMATION AGENT - ULTRA HIGH PERFORMANCE MODE

You are an Android automation specialist with MANDATORY efficiency requirements.

CRITICAL PERFORMANCE RULES (VIOLATION = FAILURE):
1. DEVICE_ID_OVERRIDE: Use device "{device_override}" for ALL mobile operations
2. NEVER call mobile_list_available_devices - device is pre-determined
3. NEVER call mobile_list_apps unless EXPLICITLY required by task
4. Execute actions using coordinates when possible (faster than element search)
5. Take screenshots ONLY when verification is explicitly required
6. Use mobile_launch_app with exact package names (no guessing)
7. Execute operations in single calls - avoid verification loops

MANDATORY EXECUTION PATTERN:
1. Use device "{device_override}" directly in all mobile_* tool calls
2. Launch apps immediately with mobile_launch_app
3. Interact using mobile_click_on_screen_at_coordinates when possible
4. Type text using mobile_type_keys with submit=true for efficiency
5. Report completion immediately after action

AVAILABLE TOOLS (Use efficiently):
- mobile_launch_app: Direct app launching (use package name directly)
- mobile_click_on_screen_at_coordinates: Preferred for clicking (fastest)
- mobile_type_keys: Direct text input with submit option
- mobile_take_screenshot: ONLY when explicitly required for verification
- mobile_list_elements_on_screen: ONLY when specific element search needed

RESPONSE REQUIREMENTS:
- Execute actions immediately without hesitation
- Keep responses brief and action-focused
- End with exact success phrase when specified in task
- Avoid explanatory text - focus on execution

DEVICE CONTEXT: All operations target "{device_override}" - use this device ID in every mobile tool call."""

    async def _connect_to_device(self, device_id: str):
        """指定されたデバイスに接続
        
        Args:
            device_id: 接続対象のAndroidデバイスID
        """
        with allure.step(f"Connect to Android device: {device_id}"):
            connect_task = f"Connect to Android device with ID: {device_id}"
            await self._execute_agent_task(connect_task)
            self._current_device_id = device_id
    
    @allure.step("Execute mobile task: {task_instruction}")
    async def validate_mobile_task(
        self,
        task_instruction: str,
        expected_substring: Optional[str] = None,
        ignore_case: bool = True,
        timeout: float = 30.0,
        device_id: Optional[str] = None,
        app_bundle_id: Optional[str] = None
    ) -> str:
        """モバイルタスクの実行と検証
        
        Browser UseのBaseAgentTest.validate_taskメソッドのAndroid版相当機能。
        指定されたタスクをMobile-MCPエージェントで実行し、結果を検証する。
        
        Args:
            task_instruction: エージェントに実行させる具体的な指示
            expected_substring: 結果に含まれることを期待する文字列
            ignore_case: 文字列比較時の大文字小文字無視フラグ
            device_id: 対象デバイスID (未指定時は現在接続中のデバイス使用)
            app_bundle_id: 対象アプリのBundle ID (指定時は事前起動)
            timeout: タスク実行のタイムアウト時間（秒）
            
        Returns:
            エージェントが返した最終結果テキスト
            
        Raises:
            AssertionError: 結果がNoneまたは期待する文字列が見つからない場合
            TimeoutError: 実行がタイムアウトした場合
        """
        
        start_time = time.time()
        
        try:
            # エージェント初期化チェック
            if not self.agent:
                await self.setup_mobile_agent(device_id)
            
            # デバイス接続（必要に応じて）
            if device_id and device_id != self._current_device_id:
                await self._connect_to_device(device_id)
            
            # アプリ起動（指定された場合）
            if app_bundle_id and app_bundle_id != self._current_app_bundle_id:
                await self._launch_application(app_bundle_id)
            
            # メインタスク実行
            allure.dynamic.description(f"Executing: {task_instruction}")
            result_text = await asyncio.wait_for(
                self._execute_agent_task(task_instruction),
                timeout=timeout
            )
            
            # 基本結果検証
            assert result_text is not None, "Agent returned None result"
            assert isinstance(result_text, str), f"Agent returned non-string result: {type(result_text)}"
            assert len(result_text.strip()) > 0, "Agent returned empty result"
            
            # 失敗条件の検証（先に実行）
            failure_indicators = [
                "failed", "error", "cannot", "unable", "not found", 
                "timed out", "aborted", "unsuccessful", "could not"
            ]
            result_lower = result_text.lower()
            for indicator in failure_indicators:
                if indicator in result_lower and expected_substring and expected_substring.lower() not in result_lower:
                    assert False, f"Task failed with indicator '{indicator}' in response: '{result_text}'"
            
            # expected_substring検証（BaseAgentTestと同じロジック）
            if expected_substring:
                result_to_check = result_text.lower() if ignore_case else result_text
                substring_to_check = (
                    expected_substring.lower() if ignore_case else expected_substring
                )
                assert (
                    substring_to_check in result_to_check
                ), f"Assertion failed: Expected '{expected_substring}' not found in agent result: '{result_text}'"
            
            # タスク成功の追加検証：十分な詳細性があるかチェック
            if len(result_text.strip()) < 20:
                allure.attach(
                    f"Warning: Very short response may indicate incomplete execution: '{result_text}'",
                    name="Response Length Warning",
                    attachment_type=allure.attachment_type.TEXT
                )
            
            # 実行時間記録
            execution_time = time.time() - start_time
            allure.attach(
                f"Task completed in {execution_time:.2f} seconds",
                name="Execution Time",
                attachment_type=allure.attachment_type.TEXT
            )
            
            return result_text
            
        except asyncio.TimeoutError:
            error_msg = f"Task execution timed out after {timeout} seconds"
            allure.attach(error_msg, name="Timeout Error", attachment_type=allure.attachment_type.TEXT)
            raise TimeoutError(error_msg)
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            allure.attach(error_msg, name="Execution Error", attachment_type=allure.attachment_type.TEXT)
            raise
    
    async def _launch_application(self, app_bundle_id: str):
        """指定されたアプリケーションを起動（高速化版）
        
        Args:
            app_bundle_id: 起動するアプリケーションのBundle ID
        """
        with allure.step(f"Launch application: {app_bundle_id}"):
            device_id = self._current_device_id or "emulator-5554"
            
            try:
                # MCPツールを取得して直接呼び出し
                mobile_tools = await self.mcp_client.get_tools()
                launch_tool = None
                
                # mobile_launch_appツールを検索
                for tool in mobile_tools:
                    if hasattr(tool, 'name') and tool.name == 'mobile_launch_app':
                        launch_tool = tool
                        break
                
                if not launch_tool:
                    raise RuntimeError("mobile_launch_app tool not found")
                    
                result = await launch_tool.ainvoke({
                    "device": device_id,
                    "packageName": app_bundle_id
                })
                
                # 結果を処理
                if result and hasattr(result, 'content'):
                    content = result.content
                    if isinstance(content, list):
                        result_text = "\n".join([item.get("text", str(item)) for item in content if isinstance(item, dict)])
                    else:
                        result_text = content
                    
                    allure.attach(
                        f"Direct app launch result: {result_text}",
                        name="App Launch Result",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    
                    self._current_app_bundle_id = app_bundle_id
                    
                    # 状態管理を更新
                    self._update_agent_state(f"Launch application: {app_bundle_id}", result_text)
                    
                else:
                    raise RuntimeError(f"Failed to launch app {app_bundle_id}")
                    
            except Exception as e:
                # フォールバック：エージェント経由で起動
                allure.attach(
                    f"Direct launch failed: {str(e)}. Falling back to agent mode.",
                    name="Launch Fallback",
                    attachment_type=allure.attachment_type.TEXT
                )
                
                launch_task = f"Launch application with bundle ID: {app_bundle_id}"
                await self._execute_agent_task(launch_task)
                self._current_app_bundle_id = app_bundle_id
    
    async def _execute_agent_task(self, task: str) -> str:
        """エージェントタスクの実行と結果取得
        
        Args:
            task: 実行するタスクの指示文
            
        Returns:
            エージェントの実行結果
        """
        with allure.step(f"Agent execution: {task}"):
            start_time = time.time()
            self._current_task_start_time = start_time  # タスク開始時間を記録
            
            try:
                # タスク実行前のスクリーンショット取得
                await self._capture_pre_task_state(task)
                
                # デバイス情報を含めたタスクメッセージを作成
                enhanced_task = await self._enhance_task_with_device_info(task)
                
                # 会話履歴を含めたメッセージを構築
                messages = self._build_conversation_with_history(enhanced_task)
                
                # エージェント実行（効率化設定）
                response = await asyncio.wait_for(
                    self.agent.ainvoke(
                        {"messages": messages},
                        config={"recursion_limit": 25}  # 15 → 25 に増加（スポーツナビゲーション対応）
                    ),
                    timeout=150  # 2.5分でタイムアウト（スポーツナビゲーション用）
                )
                
                # 結果抽出
                if not response or "messages" not in response or not response["messages"]:
                    raise RuntimeError("Invalid agent response structure")
                
                # output_version="responses/v1" 対応: contentは文字列またはリスト
                raw_result = response["messages"][-1].content
                if isinstance(raw_result, list):
                    # 新形式: リストから文字列を抽出
                    result = "\n".join([item.get("text", str(item)) for item in raw_result if isinstance(item, dict)])
                else:
                    # 従来形式: 文字列
                    result = raw_result
                
                duration = time.time() - start_time
                
                # 会話履歴を更新
                self._update_conversation_history(enhanced_task, result)
                
                # エージェント状態を更新
                self._update_agent_state(task, result)
                
                # --- 各アクション終了時の自動記録 ---
                try:
                    # conftest.pyのrecord_android_step関数を呼び出し
                    from conftest import record_android_step
                    await record_android_step(self)
                except ImportError:
                    # conftest.pyがインポートできない場合のフォールバック
                    allure.attach(
                        "record_android_step function not available",
                        name="Step Recording Warning",
                        attachment_type=allure.attachment_type.TEXT
                    )
                except Exception as step_recording_error:
                    # ステップ記録エラーは警告レベルで処理（メインタスクの失敗にしない）
                    allure.attach(
                        f"Failed to record step: {str(step_recording_error)}",
                        name="Step Recording Error",
                        attachment_type=allure.attachment_type.TEXT
                    )
                
                # パフォーマンス警告
                if duration > 60:
                    allure.attach(
                        f"Task execution took {duration:.1f}s (target: <60s)\nTask: {task}",
                        name="Performance Warning",
                        attachment_type=allure.attachment_type.TEXT
                    )
                
                # 実行後の状態とコンテキスト情報をAllureに添付
                await self._attach_mobile_context(task, result, duration)
                
                return result
                
            except asyncio.TimeoutError:
                timeout_msg = f"Task execution exceeded 120s timeout: {task}"
                allure.attach(
                    timeout_msg,
                    name="Timeout Error",
                    attachment_type=allure.attachment_type.TEXT
                )
                raise TimeoutError(timeout_msg)
                
            except Exception as e:
                # エラー情報をAllureに添付
                error_details = {
                    "Task": task,
                    "Error Type": type(e).__name__,
                    "Error Message": str(e),
                    "Execution Time": f"{time.time() - start_time:.2f}s"
                }
                
                allure.attach(
                    "\n".join([f"{k}: {v}" for k, v in error_details.items()]),
                    name="Error Details",
                    attachment_type=allure.attachment_type.TEXT
                )
                
                # エラー時のスクリーンショット取得（可能であれば）
                try:
                    await self._capture_error_screenshot()
                except Exception:
                    pass  # エラー時のスクリーンショット失敗は無視
                
                raise
    
    async def _enhance_task_with_device_info(self, task: str) -> str:
        """タスクにデバイス情報を追加して効率化
        
        Args:
            task: 元のタスク指示文
            
        Returns:
            デバイス情報が追加されたタスク指示文
        """
        device_id = self._current_device_id or "emulator-5554"
        
        device_info = f"""
DEVICE OVERRIDE: Use device "{device_id}" for ALL mobile operations.
DO NOT call mobile_list_available_devices - device is already determined.
Execute all mobile_* tool calls with device parameter set to "{device_id}".

"""
        return device_info + task

    async def _capture_pre_task_state(self, task: str):
        """タスク実行前の画面状態をキャプチャ
        
        Args:
            task: 実行予定のタスク
        """
        try:
            # タスク実行前のスクリーンショット
            await self._attach_current_screenshot(f"Pre-task: {task}")
        except Exception:
            # スクリーンショット取得失敗は警告レベルで記録
            allure.attach(
                "Failed to capture pre-task screenshot",
                name="Screenshot Warning",
                attachment_type=allure.attachment_type.TEXT
            )
    
    async def _attach_mobile_context(self, task: str, result: str, duration: float):
        """モバイルテスト実行コンテキストのAllure添付
        
        BaseAgentTestのrecord_step機能に相当する情報を記録
        
        Args:
            task: 実行されたタスク
            result: 実行結果
            duration: 実行時間
        """
        
        # エージェント実行結果を添付
        allure.attach(
            result,
            name=f"Agent Result - {task[:50]}...",
            attachment_type=allure.attachment_type.TEXT
        )
        
        # 実行時間を記録
        allure.attach(
            f"Task: {task}\nDuration: {duration:.2f} seconds\nResult Length: {len(result)} characters",
            name="Execution Summary",
            attachment_type=allure.attachment_type.TEXT
        )
        
        # タスク実行後のスクリーンショット取得・添付
        await self._attach_current_screenshot(f"Post-task: {task}")
        
        # アクセシビリティツリー情報取得・添付
        await self._attach_accessibility_tree(task)
        
        # 現在のアプリ状態情報取得・添付
        await self._attach_app_state_info()
    
    async def _attach_current_screenshot(self, context: str):
        """現在の画面のスクリーンショットを取得してAllureに添付
        
        mobile_save_screenshotツールを使用してファイルパスベースでスクリーンショットを取得
        
        Args:
            context: スクリーンショットのコンテキスト情報
        """
        try:
            if not self.mcp_client:
                allure.attach(
                    "MCP client not available for screenshot capture",
                    name=f"Screenshot Error - {context}",
                    attachment_type=allure.attachment_type.TEXT
                )
                return
            
            # Mobile-MCPツールを取得して直接呼び出し（LLMを経由せず）
            mobile_tools = await self.mcp_client.get_tools()
            screenshot_tool = None
            
            # mobile_save_screenshotツールを検索
            for tool in mobile_tools:
                if hasattr(tool, 'name') and tool.name == 'mobile_save_screenshot':
                    screenshot_tool = tool
                    break
            
            if not screenshot_tool:
                allure.attach(
                    "mobile_save_screenshot tool not found in available tools",
                    name=f"Screenshot Tool Error - {context}",
                    attachment_type=allure.attachment_type.TEXT,
                )
                return
                
            # device パラメータを使ってスクリーンショットを保存（タイムアウト保護付き）
            device_id = self._current_device_id or "emulator-5554"
            
            # 一時ファイルパスを生成
            import tempfile
            import os
            temp_dir = tempfile.gettempdir()
            screenshot_filename = f"android_screenshot_{int(time.time())}.png"
            screenshot_path = os.path.join(temp_dir, screenshot_filename)
            
            screenshot_result = await asyncio.wait_for(
                screenshot_tool.ainvoke({
                    "device": device_id,
                    "saveTo": screenshot_path
                }),
                timeout=15.0  # 15秒のタイムアウト
            )
            
            # デバッグ: screenshot_resultの内容をログ出力
            print(f"DEBUG _attach_current_screenshot: screenshot_result type: {type(screenshot_result)}")
            print(f"DEBUG _attach_current_screenshot: screenshot_result: {screenshot_result}")
            print(f"DEBUG _attach_current_screenshot: screenshot_path: {screenshot_path}")
            
            # mobile_save_screenshotの結果は保存が成功したことを示す（パスまたは成功メッセージ）
            # 実際のファイルパスはscreenshot_pathに指定したパス
            if os.path.exists(screenshot_path):
                try:
                    # ファイルを読み込んでAllureに添付
                    with open(screenshot_path, 'rb') as f:
                        screenshot_bytes = f.read()
                    
                    # ファイル拡張子から画像形式を判定
                    if screenshot_path.lower().endswith('.jpg') or screenshot_path.lower().endswith('.jpeg'):
                        attachment_type = allure.attachment_type.JPG
                    elif screenshot_path.lower().endswith('.png'):
                        attachment_type = allure.attachment_type.PNG
                    else:
                        # ファイルヘッダーから判定
                        if screenshot_bytes.startswith(b'\xff\xd8\xff'):
                            attachment_type = allure.attachment_type.JPG
                        elif screenshot_bytes.startswith(b'\x89PNG'):
                            attachment_type = allure.attachment_type.PNG
                        else:
                            attachment_type = allure.attachment_type.PNG  # デフォルト
                    
                    allure.attach(
                        screenshot_bytes,
                        name=f"Screenshot - {context}",
                        attachment_type=attachment_type
                    )
                    print(f"DEBUG: スクリーンショットをAllureに添付完了: {screenshot_path}")
                    
                    # 一時ファイルを削除
                    try:
                        os.remove(screenshot_path)
                    except Exception:
                        pass  # 削除失敗は無視
                    
                    return
                        
                except Exception as e:
                    allure.attach(
                        f"Failed to read screenshot file: {str(e)}",
                        name=f"Screenshot File Read Error - {context}",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    return
            else:
                allure.attach(
                    f"Screenshot file not found at: {screenshot_path}",
                    name=f"Screenshot File Error - {context}",
                    attachment_type=allure.attachment_type.TEXT
                )
                return
            
            # mobile_save_screenshotツールから有効な結果が得られなかった場合
            allure.attach(
                f"No valid screenshot path returned from mobile_save_screenshot: {screenshot_result}",
                name=f"Screenshot Tool Response Error - {context}",
                attachment_type=allure.attachment_type.TEXT
            )
                        
        except asyncio.TimeoutError:
            allure.attach(
                f"Screenshot capture timed out after 15 seconds",
                name=f"Screenshot Timeout - {context}",
                attachment_type=allure.attachment_type.TEXT
            )
        except Exception as e:
            allure.attach(
                f"Failed to capture screenshot: {str(e)}",
                name=f"Screenshot Error - {context}",
                attachment_type=allure.attachment_type.TEXT
            )
    
    async def _attach_accessibility_tree(self, task: str):
        """アクセシビリティツリー情報を取得してAllureに添付
        
        Args:
            task: 関連するタスク情報
        """
        try:
            if not self.agent:
                return
                
            tree_response = await self.agent.ainvoke({
                "messages": [HumanMessage(content="Get the accessibility tree of the current screen")]
            })
            
            # output_version="responses/v1" 対応
            raw_tree_content = tree_response["messages"][-1].content
            if isinstance(raw_tree_content, list):
                tree_content = "\n".join([item.get("text", str(item)) for item in raw_tree_content if isinstance(item, dict)])
            else:
                tree_content = raw_tree_content
            
            if tree_content and isinstance(tree_content, str):
                allure.attach(
                    tree_content,
                    name=f"Accessibility Tree - {task[:30]}...",
                    attachment_type=allure.attachment_type.XML
                )
        except Exception as e:
            allure.attach(
                f"Failed to capture accessibility tree: {str(e)}",
                name="Accessibility Tree Error",
                attachment_type=allure.attachment_type.TEXT
            )
    
    async def _attach_app_state_info(self):
        """現在のアプリケーション状態情報を取得してAllureに添付"""
        try:
            if not self.agent:
                return
            
            # タイムアウトを設定してAPIリクエストを保護
            app_info_response = await asyncio.wait_for(
                self.agent.ainvoke({
                    "messages": [HumanMessage(content="Get current application information")]
                }),
                timeout=10.0  # 10秒のタイムアウト
            )
            
            # output_version="responses/v1" 対応
            raw_app_info = app_info_response["messages"][-1].content
            if isinstance(raw_app_info, list):
                app_info = "\n".join([item.get("text", str(item)) for item in raw_app_info if isinstance(item, dict)])
            else:
                app_info = raw_app_info
            
            if app_info and isinstance(app_info, str):
                allure.attach(
                    app_info,
                    name="Current App State",
                    attachment_type=allure.attachment_type.TEXT
                )
        except asyncio.TimeoutError:
            # アプリ状態取得がタイムアウトした場合
            allure.attach(
                "App state info request timed out after 10 seconds",
                name="App State Timeout",
                attachment_type=allure.attachment_type.TEXT
            )
        except Exception as e:
            # その他のエラーの場合、詳細を記録
            allure.attach(
                f"Failed to get app state info: {str(e)}",
                name="App State Error", 
                attachment_type=allure.attachment_type.TEXT
            )
    
    async def _capture_error_screenshot(self):
        """エラー発生時の緊急スクリーンショット取得"""
        try:
            await self._attach_current_screenshot("Error State")
        except Exception:
            # エラー時のスクリーンショット取得失敗は無視
            pass
    
    async def cleanup(self):
        """リソースのクリーンアップ"""
        try:
            if self.mcp_client:
                # MCP クライアントのクリーンアップ
                # Note: 具体的なクリーンアップ方法はlangchain-mcp-adaptersの実装に依存
                pass
        except Exception:
            pass
        
        self.mcp_client = None
        self.agent = None
        self._current_device_id = None
        self._current_app_bundle_id = None


# BaseAgentTestとの互換性のためのヘルパー関数
async def run_mobile_agent_task(
    llm: ChatOpenAI,
    task_instruction: str,
    device_id: Optional[str] = None,
    timeout: float = 120.0
) -> str:
    """Mobile-MCP版のrun_agent_task相当機能
    
    既存のBaseAgentTestのrun_agent_task関数のAndroid版。
    一時的なエージェントインスタンスでタスクを実行する。
    
    Args:
        llm: 使用する言語モデル
        task_instruction: 実行するタスク指示
        device_id: 対象デバイスID
        timeout: タイムアウト時間
        
    Returns:
        エージェントの実行結果
    """
    android_agent = AndroidBaseAgentTest()
    android_agent.llm = llm
    
    try:
        await android_agent.setup_mobile_agent(device_id)
        result = await android_agent._execute_agent_task(task_instruction)
        return result
    finally:
        await android_agent.cleanup()


# 状態管理メソッドの実装を AndroidBaseAgentTest クラスに追加
def _add_state_management_methods():
    """状態管理メソッドをAndroidBaseAgentTestクラスに追加"""
    
    def _build_conversation_with_history(self, current_task: str):
        """会話履歴を含めたメッセージを構築"""
        messages = []
        device_id = self._current_device_id or "emulator-5554"
        
        # 過去の重要な操作履歴を含める（最近の5件まで）
        if self.conversation_history:
            history_summary = "PREVIOUS OPERATIONS:\n"
            for entry in self.conversation_history[-5:]:  # 最近の5件
                history_summary += f"- {entry['task']} -> {entry['result'][:100]}...\n"
            
            # デバイス状態情報を強制追加
            history_summary += f"\nDEVICE OVERRIDE: Use device '{device_id}' for ALL operations.\n"
            history_summary += "CRITICAL: Never call mobile_list_available_devices - device is predetermined.\n"
            
            if self.agent_state.current_app:
                history_summary += f"CURRENT APP: {self.agent_state.current_app}\n"
                
            # システムメッセージとして履歴を追加
            messages.append(HumanMessage(content=f"{history_summary}\nCURRENT TASK: {current_task}"))
        else:
            # 初回でもデバイス情報を明示
            device_context = f"DEVICE OVERRIDE: Use device '{device_id}' for ALL mobile operations.\nNEVER call mobile_list_available_devices.\n\n"
            messages.append(HumanMessage(content=device_context + current_task))
            
        return messages
    
    def _update_conversation_history(self, task: str, result: str):
        """会話履歴を更新"""
        self.conversation_history.append({
            "task": task,
            "result": result,
            "timestamp": time.time(),
            "start_time": getattr(self, '_current_task_start_time', time.time())  # タスク開始時間
        })
        
        # 履歴が長くなりすぎないよう制限（最新10件まで）
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    def _update_agent_state(self, task: str, result: str):
        """エージェント状態を更新"""
        # 結果が文字列でない場合の処理（output_version="responses/v1"対応）
        if not isinstance(result, str):
            if isinstance(result, list):
                result = "\n".join([item.get("text", str(item)) for item in result if isinstance(item, dict)])
            else:
                result = str(result)
        
        # デバイスIDを検出してキャッシュを更新
        if "emulator-" in result or "device" in result.lower():
            if "emulator-" in result:
                import re
                device_match = re.search(r'emulator-\d+', result)
                if device_match:
                    device_id = device_match.group()
                    self.agent_state.device_id = device_id
                    self._current_device_id = device_id
                    # キャッシュも更新
                    self._device_cache['device_id'] = device_id
                    self._device_cache['timestamp'] = time.time()
        
        # アプリ起動を検出
        if "launch" in task.lower() or "open" in task.lower():
            if "chrome" in task.lower():
                self.agent_state.current_app = "com.android.chrome"
        
        # 操作履歴に追加
        operation_summary = f"{task} -> {result[:50]}..."
        self.agent_state.operation_history.append(operation_summary)
        
        # 履歴制限（最新5件まで）
        if len(self.agent_state.operation_history) > 5:
            self.agent_state.operation_history = self.agent_state.operation_history[-5:]
    
    # メソッドをクラスに追加
    AndroidBaseAgentTest._build_conversation_with_history = _build_conversation_with_history
    AndroidBaseAgentTest._update_conversation_history = _update_conversation_history
    AndroidBaseAgentTest._update_agent_state = _update_agent_state

# 状態管理メソッドを追加
_add_state_management_methods()
