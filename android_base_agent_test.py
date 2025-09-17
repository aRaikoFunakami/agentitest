"""
Android Base Agent Test
Pythonの単体テストからLLMエージェントを使ってAndroidアプリの自動操作テストを実行
"""

import asyncio
import time
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from colorama import Fore, Style, init

import allure
from langgraph.prebuilt import create_react_agent
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.client import MultiServerMCPClient

init(autoreset=True)

@dataclass
class AgentState:
    """エージェントの状態管理"""
    device_id: Optional[str] = None
    current_app: Optional[str] = None
    operation_history: List[str] = None
    
    def __post_init__(self):
        if self.operation_history is None:
            self.operation_history = []

class EventPrinter:
    """Pretty-printer for LangGraph astream_events.
    This class prints only observable signals (no chain-of-thought):
    - node start/end
    - LLM streaming tokens (optional)
    - final LLM outputs when provider buffers
    - tool start/end with args and outputs
    Configuration can be passed at construction for reuse.
    """

    def __init__(self,
                 verbose: bool = False):
        self.verbose = verbose
        self.event_log = []  # イベントログを保持

    def _log_and_attach(self, message: str, event_type: str = "Event"):
        """print実行とallure.attachを両方行うラッパー関数
        
        Args:
            message: ログメッセージ
            event_type: イベントタイプ（Allure添付時の名前に使用）
        """
        # コンソールに出力
        print(Fore.BLUE + message)
        
        # イベントログに追加
        self.event_log.append(f"{time.time():.3f}: {message}")
        
        # Allureに添付（リアルタイム）
        try:
            allure.attach(
                message,
                name=f"Agent {event_type}",
                attachment_type=allure.attachment_type.TEXT
            )
        except Exception:
            # Allure添付失敗は無視（テスト実行は継続）
            pass

    def get_complete_log(self) -> str:
        """完全なイベントログを取得"""
        return "\n".join(self.event_log)

    def attach_complete_log(self):
        """完全なイベントログをAllureに添付"""
        if self.event_log:
            complete_log = self.get_complete_log()
            try:
                allure.attach(
                    complete_log,
                    name="Complete Agent Event Log",
                    attachment_type=allure.attachment_type.TEXT
                )
            except Exception:
                pass

    # --- public handlers ---
    def on_node_start(self, ev):
        node = ev.get("data", {}).get("node_name")
        self._log_and_attach(
            f"[NODE:START] {node}",
            "Node Start"
        )

    def on_node_end(self, ev):
        node = ev.get("data", {}).get("node_name")
        self._log_and_attach(
            f"[NODE:END] {node}",
            "Node End"
        )

    def on_tool_start(self, ev):
        d = ev.get("data", {})
        name = ev.get("name") or "<tool>"
        self._log_and_attach(
            f"[TOOL:START] {name} args={d.get('input')}",
            "Tool Start"
        )

    def on_tool_end(self, ev):
        d = ev.get("data", {})
        name = ev.get("name") or "<tool>"
        output_content = d.get('output')
        if hasattr(output_content, 'content'):
            output_display = output_content.content
        else:
            output_display = str(output_content)
        
        self._log_and_attach(
            f"[TOOL:END] {name} output={output_display}",
            "Tool End"
        )

    def _print_on_chat_model_end(self, ev):
        # ev['data']['output'] が AIMessage インスタンス
        ai_msg = ev['data']['output'].content
        self._log_and_attach(f"[MODEL:END] {ai_msg}","Model End")

    def _print_on_chain_start(self, ev):
        if self.verbose:
            self._log_and_attach(f"[CHAIN:START] {ev.get('name')}","Chain Start")

    def _print_on_chain_end(self, ev):
        data = ev.get('data', {})
        output = data.get('output')
        if ev.get('name') == 'should_continue' and output:
            message = "[CHAIN:END] should_continue, " + (output if not isinstance(output, list) else str(output[0]))
            self._log_and_attach(message, "Chain End")
        elif self.verbose:
            self._log_and_attach(f"[CHAIN:END] {ev.get('name')},","Chain End")

    def dispatch(self, ev):
        et = ev.get("event", "")
        
        if et.endswith("node_start"):
            self.on_node_start(ev)
        elif et.endswith("node_end"):
            self.on_node_end(ev)
        elif et.endswith("tool_start"):
            self.on_tool_start(ev)
        elif et.endswith("tool_end"):
            self.on_tool_end(ev)
        elif et.endswith("on_chat_model_end"):
            self._print_on_chat_model_end(ev)
        elif et.endswith("on_chain_start"):
            self._print_on_chain_start(ev)
        elif et.endswith("on_chain_end"):
            self._print_on_chain_end(ev)

class AndroidBaseAgentTest:
    """Android アプリケーション自動化テスト用の基底クラス
    
    Mobile-MCPを使用してAndroidデバイス上でアプリケーションテストを実行する。
    既存のBaseAgentTestクラスのAndroid版相当機能を提供。
    """

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
        self.llm = init_chat_model("openai:gpt-4.1", temperature=0)
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
        await self._initialize_react_agent()
    
    
    async def _initialize_react_agent(self):
        """MCP クライアントの初期化"""
        self.mcp_client = MultiServerMCPClient({
            "mobile": {
                "transport": "stdio",
                "command": "/opt/homebrew/opt/node@20/bin/npx",
                "args": ["-y", "@mobilenext/mobile-mcp@latest"],
            }
        })
        
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
       return """あなたはAndroidデバイス上でアプリケーションを操作するエージェントです。
        ユーザーの指示に従ってAndroidエミュレータもしくは実機を操作しなさい。
        """
    
    @allure.step("Execute mobile task: {task}")
    async def validate_mobile_task(
        self,
        task: str,
        expected_substring: Optional[str] = None,
        ignore_case: bool = True,
        timeout: float = 30.0,
    ) -> str:
        
        start_time = time.time()

        print(Fore.YELLOW + f"\n=== Executing mobile task ===\nInstruction: {task}\nExpected substring: {expected_substring}\nTimeout: {timeout}s\n")
        
        try:
            # メインタスク実行
            allure.dynamic.description(f"Executing: {task}")

            # タスク実行前のスクリーンショット取得
            await self._capture_pre_task_state(task)

            post_task_message = "\nタスクを実行するために必要な操作を計画しなさい。次に計画を１つ１つ実行しなさい。"
            inputs = {"messages": [
                ("user", f"{task}"),
                ("user", post_task_message)
            ]}
            result_text = None
            printer = EventPrinter()
            async for ev in self.agent.astream_events(inputs, version="v2"):
                printer.dispatch(ev)
                if ev.get("event", "").endswith("on_chat_model_end"):
                    final_message = ev.get("data", {}).get("output")
                    print(f"DEBUG: final_message: {final_message}")
            
            # EventPrinterの完全ログをAllureに添付
            printer.attach_complete_log()
            
            result_text = final_message.content
            #result_text = final_message

            print(Fore.YELLOW + f"\n=== Finish self.agent.astream_events ===\n {final_message.content}\n{'='*50}\n")

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

            # テスト結果を記録
            await self._attach_final_results(task, result_text, execution_time)
             
            return result_text
            
        except asyncio.TimeoutError:
            error_msg = f"Task execution timed out after {timeout} seconds"
            allure.attach(error_msg, name="Timeout Error", attachment_type=allure.attachment_type.TEXT)
            raise TimeoutError(error_msg)
        except Exception as e:
            error_msg = f"Task execution failed: {str(e)}"
            allure.attach(error_msg, name="Execution Error", attachment_type=allure.attachment_type.TEXT)
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
    
    async def _attach_final_results(self, task: str, result: str, duration: float):
        """モバイルテスト実行コンテキストのAllure添付
        
        BaseAgentTestのrecord_step機能に相当する情報を記録
        
        Args:
            task: 実行されたタスク
            result: 実行結果
            duration: 実行時間
        """
        print(Fore.BLUE + f"Attaching final results: {task[:50]}...")
        
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
            print(f"DEBUG: _attach_accessibility_tree starting for task: {task[:30]}...")
            
            if not self.mcp_client:
                print("DEBUG: MCP client not available")
                allure.attach(
                    "MCP client not available for accessibility tree capture",
                    name=f"Accessibility Tree Error - {task[:30]}...",
                    attachment_type=allure.attachment_type.TEXT
                )
                return
            
            # Mobile-MCPツールを取得
            print("DEBUG: Getting mobile tools...")
            mobile_tools = await self.mcp_client.get_tools()
            accessibility_tool = None
            
            # mobile_list_elements_on_screenツールを検索
            print("DEBUG: Searching for mobile_list_elements_on_screen tool...")
            for tool in mobile_tools:
                if hasattr(tool, 'name') and tool.name == 'mobile_list_elements_on_screen':
                    accessibility_tool = tool
                    print("DEBUG: Found mobile_list_elements_on_screen tool")
                    break
            
            if not accessibility_tool:
                print("DEBUG: mobile_list_elements_on_screen tool not found")
                allure.attach(
                    "mobile_list_elements_on_screen tool not found in available tools",
                    name=f"Accessibility Tool Error - {task[:30]}...",
                    attachment_type=allure.attachment_type.TEXT
                )
                return
            
            # デバイスIDを使って画面要素を取得（タイムアウト保護付き）
            device_id = self._current_device_id or "emulator-5554"
            print(f"DEBUG: Invoking accessibility tool with device: {device_id}")
            
            tree_result = await asyncio.wait_for(
                accessibility_tool.ainvoke({
                    "device": device_id
                }),
                timeout=15.0  # 15秒のタイムアウト
            )
            
            print(f"DEBUG: Got tree_result type: {type(tree_result)}")
            print(f"DEBUG: tree_result content preview: {str(tree_result)[:100]}...")
            
            # ツールの結果を文字列として処理
            if isinstance(tree_result, str):
                tree_content = tree_result
                print("DEBUG: Using tree_result as string")
            elif hasattr(tree_result, 'content'):
                tree_content = tree_result.content
                print("DEBUG: Using tree_result.content")
            else:
                tree_content = str(tree_result)
                print("DEBUG: Converting tree_result to string")
            
            print(f"DEBUG: Final tree_content length: {len(tree_content) if tree_content else 0}")
            
            if tree_content and len(tree_content.strip()) > 0:
                print("DEBUG: Attaching accessibility tree to Allure")
                allure.attach(
                    tree_content,
                    name=f"Accessibility Tree - {task[:30]}...",
                    attachment_type=allure.attachment_type.TEXT  # JSONではなくTEXTに変更
                )
                print("DEBUG: Successfully attached accessibility tree")
            else:
                print("DEBUG: No tree content, attaching empty message")
                allure.attach(
                    "No accessibility tree data returned",
                    name=f"Accessibility Tree Empty - {task[:30]}...",
                    attachment_type=allure.attachment_type.TEXT
                )
                
        except asyncio.TimeoutError:
            print("DEBUG: Accessibility tree capture timed out")
            allure.attach(
                "Accessibility tree capture timed out after 15 seconds",
                name=f"Accessibility Tree Timeout - {task[:30]}...",
                attachment_type=allure.attachment_type.TEXT
            )
        except Exception as e:
            print(f"DEBUG: Exception in _attach_accessibility_tree: {str(e)}")
            allure.attach(
                f"Failed to capture accessibility tree: {str(e)}",
                name="Accessibility Tree Error",
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

    # AndroidBaseTestのユーティリティメソッドをマージ
    @staticmethod
    def assert_task_success(result: str, expected_substring: Optional[str] = None):
        """
        タスク実行結果の成功をアサート
        
        Args:
            result: エージェントからの実行結果
            expected_substring: 期待される部分文字列（オプション）
        """
        assert result is not None, "Agent did not return a result"
        assert "error" not in result.lower(), f"Task failed with error: {result}"
        
        if expected_substring:
            assert expected_substring.lower() in result.lower(), \
                f"Expected '{expected_substring}' not found in result: {result}"
    
    @staticmethod 
    def assert_screenshot_captured(result: str):
        """
        スクリーンショットが正常にキャプチャされたことをアサート
        """
        success_indicators = [
            "screenshot", "captured", "image", "taken",
            "visual", "display", "screen"
        ]
        
        result_lower = result.lower()
        assert any(indicator in result_lower for indicator in success_indicators), \
            f"Screenshot capture not confirmed in result: {result}"

