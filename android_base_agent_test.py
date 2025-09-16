"""
Android版BaseAgentTestクラス実装

Mobile-MCPを使用してAndroidアプリケーションの自動化テストを実行する基底クラス
"""

import asyncio
import time
import os
import base64
from typing import Optional, Dict, Any
import allure
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent


class AndroidBaseAgentTest:
    """Android アプリケーション自動化テスト用の基底クラス
    
    Mobile-MCPを使用してAndroidデバイス上でアプリケーションテストを実行する。
    既存のBaseAgentTestクラスのAndroid版相当機能を提供。
    """
    
    # デフォルト設定
    DEFAULT_APP_BUNDLE_ID = "com.android.chrome"
    APPIUM_SERVER_URL = "http://localhost:4723"
    MCP_SERVER_TIMEOUT = 30.0
    
    def __init__(self):
        """AndroidBaseAgentTestインスタンスの初期化"""
        self.mcp_client: Optional[MultiServerMCPClient] = None
        self.agent = None
        self.llm = ChatOpenAI(
            model="gpt-4-turbo",
            temperature=0,
            timeout=60,
            max_retries=2
        )
        self._current_device_id: Optional[str] = None
        self._current_app_bundle_id: Optional[str] = None
    
    async def setup_mobile_agent(self, device_id: Optional[str] = None):
        """モバイルエージェントの初期化とセットアップ
        
        Args:
            device_id: 接続対象のAndroidデバイスID (省略時は自動検出)
        """
        await self._initialize_mcp_client()
        await self._initialize_react_agent()
        
        if device_id:
            await self._connect_to_device(device_id)
    
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
        self.agent = create_react_agent(
            self.llm,
            mobile_tools,
            prompt=self._get_mobile_agent_prompt()
        )
    
    def _get_mobile_agent_prompt(self) -> str:
        """モバイルエージェント用のシステムプロンプト
        
        Returns:
            エージェントに与えるシステムプロンプト文字列
        """
        return """You are a skilled mobile app testing assistant for Android devices.

Your capabilities include:
- Taking screenshots of the current screen
- Getting accessibility tree information for element identification
- Tapping elements by coordinates or accessibility identifiers
- Typing text input in text fields
- Performing swipe and scroll gestures
- Launching and managing applications
- Navigating between different apps and screens

Guidelines for successful testing:
1. Always take a screenshot first to understand the current screen state
2. Use accessibility tree information to accurately locate elements before tapping
3. Wait for screen transitions to complete before proceeding
4. Be precise with coordinates and element identification
5. When completing a task successfully, always end your response with the exact phrase specified in the task instructions

This ending phrase is crucial for test validation and must be included exactly as specified."""

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
        ignore_case: bool = False,
        device_id: Optional[str] = None,
        app_bundle_id: Optional[str] = None,
        timeout: float = 120.0
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
            
            # expected_substring検証（BaseAgentTestと同じロジック）
            if expected_substring:
                result_to_check = result_text.lower() if ignore_case else result_text
                substring_to_check = (
                    expected_substring.lower() if ignore_case else expected_substring
                )
                assert (
                    substring_to_check in result_to_check
                ), f"Assertion failed: Expected '{expected_substring}' not found in agent result: '{result_text}'"
            
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
        """指定されたアプリケーションを起動
        
        Args:
            app_bundle_id: 起動するアプリケーションのBundle ID
        """
        with allure.step(f"Launch application: {app_bundle_id}"):
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
            
            try:
                # タスク実行前のスクリーンショット取得
                await self._capture_pre_task_state(task)
                
                # エージェント実行
                response = await self.agent.ainvoke({
                    "messages": [HumanMessage(content=task)]
                })
                
                # 結果抽出
                if not response or "messages" not in response or not response["messages"]:
                    raise RuntimeError("Invalid agent response structure")
                
                result = response["messages"][-1].content
                duration = time.time() - start_time
                
                # 実行後の状態とコンテキスト情報をAllureに添付
                await self._attach_mobile_context(task, result, duration)
                
                return result
                
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
        
        Args:
            context: スクリーンショットのコンテキスト情報
        """
        try:
            if not self.agent:
                return
                
            screenshot_response = await self.agent.ainvoke({
                "messages": [HumanMessage(content="Take a screenshot of the current screen")]
            })
            
            screenshot_content = screenshot_response["messages"][-1].content
            
            # Base64エンコードされた画像データの場合
            if screenshot_content and isinstance(screenshot_content, str):
                try:
                    # Base64デコードを試行
                    screenshot_bytes = base64.b64decode(screenshot_content)
                    allure.attach(
                        screenshot_bytes,
                        name=f"Screenshot - {context}",
                        attachment_type=allure.attachment_type.PNG
                    )
                except Exception:
                    # Base64デコードに失敗した場合はテキストとして添付
                    allure.attach(
                        screenshot_content,
                        name=f"Screenshot Data - {context}",
                        attachment_type=allure.attachment_type.TEXT
                    )
        except Exception as e:
            allure.attach(
                f"Failed to capture screenshot: {str(e)}",
                name="Screenshot Error",
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
            
            tree_content = tree_response["messages"][-1].content
            
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
                
            app_info_response = await self.agent.ainvoke({
                "messages": [HumanMessage(content="Get current application information")]
            })
            
            app_info = app_info_response["messages"][-1].content
            
            if app_info and isinstance(app_info, str):
                allure.attach(
                    app_info,
                    name="Current App State",
                    attachment_type=allure.attachment_type.TEXT
                )
        except Exception:
            # アプリ状態取得の失敗は無視（オプション機能のため）
            pass
    
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
