"""
Android版conftest.py

Mobile-MCPを使用したAndroidテスト用のpytest設定ファイル
"""

import asyncio
import logging
import os
import sys
from typing import Optional
import platform

import allure
import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def android_environment_reporter(request: pytest.FixtureRequest):
    """
    Android環境の詳細をレポート用に出力する
    """
    allure_dir = request.config.getoption("--alluredir")
    if not allure_dir or not isinstance(allure_dir, str):
        return

    ENVIRONMENT_PROPERTIES_FILENAME = "environment.properties"
    properties_file = os.path.join(allure_dir, ENVIRONMENT_PROPERTIES_FILENAME)

    # ディレクトリ作成
    try:
        os.makedirs(allure_dir, exist_ok=True)
    except PermissionError:
        logging.error(f"Permission denied to create report directory: {allure_dir}")
        return

    env_props = {
        "operating_system": f"{platform.system()} {platform.release()}",
        "python_version": sys.version.split(" ")[0],
        "test_framework": "pytest with mobile-mcp",
        "mobile_automation": "mobile-mcp + Appium",
        "target_platform": "Android",
        "llm_model": "gpt-4o (OpenAI)",
        "agent_framework": "LangGraph ReAct Agent",
    }

    try:
        with open(properties_file, "w") as f:
            for key, value in env_props.items():
                f.write(f"{key}={value}\n")
    except IOError as e:
        logging.error(f"Failed to write environment properties file: {e}")


@pytest.fixture(scope="session")
def android_session_config():
    """Androidテストセッション全体の設定"""
    return {
        "timeout": 300,  # 5分のデフォルトタイムアウト
        "retry_count": 3,
        "screenshot_on_failure": True,
        "accessibility_tree_on_failure": True,
    }


@pytest.fixture(scope="function")
async def android_agent_session(android_session_config):
    """
    各テスト関数用のAndroidエージェントセッション
    
    AndroidBaseAgentTestのインスタンスを作成し、テスト完了後にクリーンアップを行う
    """
    from android_base_agent_test import AndroidBaseAgentTest
    
    agent = AndroidBaseAgentTest()
    
    try:
        # エージェントのセットアップ
        await agent.setup_mobile_agent()
        yield agent
    finally:
        # クリーンアップ
        try:
            await agent.cleanup()
        except Exception as e:
            logging.warning(f"Agent cleanup failed: {e}")


@pytest.fixture(autouse=True)
def android_test_logging(request):
    """
    各Androidテスト用のログ設定
    """
    test_name = request.node.name
    logging.info(f"Starting Android test: {test_name}")
    
    yield
    
    logging.info(f"Completed Android test: {test_name}")


# pytest-asyncio設定
def pytest_configure(config):
    """
    pytest設定の初期化
    """
    # Androidテスト用のマーカー登録
    config.addinivalue_line(
        "markers", "android: mark test as Android mobile test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running test"
    )
    config.addinivalue_line(
        "markers", "browser: mark test as browser-based test"
    )


# テスト失敗時のスクリーンショット撮影
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """
    テスト失敗時に自動的にスクリーンショットとコンテキスト情報を取得
    """
    outcome = yield
    report = outcome.get_result()
    
    # テスト失敗時のみ実行
    if report.when == "call" and report.failed:
        # Androidエージェントのアクセスを試行
        if hasattr(item.instance, 'android_agent'):
            agent = item.instance.android_agent
            if agent and agent.agent:
                try:
                    # 失敗時のコンテキスト情報を非同期で取得
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 既にイベントループが実行中の場合は新しいタスクとして実行
                        asyncio.create_task(_capture_failure_context(agent, item.name))
                    else:
                        # イベントループが実行されていない場合は新しく実行
                        loop.run_until_complete(_capture_failure_context(agent, item.name))
                except Exception as e:
                    logging.error(f"Failed to capture failure context: {e}")


async def _capture_failure_context(agent, test_name: str):
    """
    テスト失敗時のコンテキスト情報をキャプチャ
    """
    try:
        # スクリーンショット取得（LLMを経由せずに直接ツール呼び出し）
        await _capture_mobile_screenshot(agent, f"Test Failure: {test_name}")
        
        # アクセシビリティツリー取得
        await agent._attach_accessibility_tree(f"Test Failure: {test_name}")
        
        # 現在のアプリ状態情報取得
        await agent._attach_app_state_info()
        
    except Exception as e:
        # エラーメッセージをAllureに添付
        allure.attach(
            f"Failed to capture context during test failure: {str(e)}",
            name="Context Capture Error",
            attachment_type=allure.attachment_type.TEXT
        )


async def _capture_mobile_screenshot(agent, context: str):
    """
    Mobile-MCPツールから直接スクリーンショットを取得してAllureに添付
    
    conftest_web.pyのscreenshot_b64 = await agent.browser_session.take_screenshot()と同等の
    直接ツール呼び出し機能をMobile-MCP版で実装
    
    Args:
        agent: AndroidBaseAgentTestインスタンス
        context: スクリーンショットのコンテキスト情報
    """
    try:
        if not agent.mcp_client:
            allure.attach(
                "MCP client not available for screenshot capture",
                name=f"Screenshot Error - {context}",
                attachment_type=allure.attachment_type.TEXT,
            )
            return
        
        # Mobile-MCPツールを取得して直接呼び出し（LLMを経由せず）
        mobile_tools = await agent.mcp_client.get_tools()
        screenshot_tool = None
        
        # mobile_take_screenshotツールを検索
        for tool in mobile_tools:
            if hasattr(tool, 'name') and tool.name == 'mobile_take_screenshot':
                screenshot_tool = tool
                break
        
        if not screenshot_tool:
            allure.attach(
                "mobile_take_screenshot tool not found in available tools",
                name=f"Screenshot Tool Error - {context}",
                attachment_type=allure.attachment_type.TEXT,
            )
            return
            
        # device パラメータを使ってスクリーンショットを取得
        device_id = agent._current_device_id or "emulator-5554"
        screenshot_result = await screenshot_tool.ainvoke({"device": device_id})
        
        # デバッグ: screenshot_resultの内容をログ出力
        print(f"DEBUG: screenshot_result type: {type(screenshot_result)}")
        print(f"DEBUG: screenshot_result length: {len(screenshot_result) if isinstance(screenshot_result, str) else 'N/A'}")
        print(f"DEBUG: screenshot_result content preview: {repr(screenshot_result[:200]) if isinstance(screenshot_result, str) else screenshot_result}")
        if hasattr(screenshot_result, 'content'):
            print(f"DEBUG: content type: {type(screenshot_result.content)}")
            print(f"DEBUG: content: {screenshot_result.content}")
        
        # mobile-mcpツールの戻り値は直接Base64文字列の可能性がある
        if isinstance(screenshot_result, str) and screenshot_result:
            try:
                # Base64文字列として直接処理を試行
                import base64
                screenshot_bytes = base64.b64decode(screenshot_result)
                
                # 画像データかどうか確認（JPEGまたはPNGヘッダーをチェック）
                if screenshot_bytes.startswith(b'\xff\xd8\xff'):
                    # JPEG画像
                    allure.attach(
                        screenshot_bytes,
                        name=f"Screenshot - {context}",
                        attachment_type=allure.attachment_type.JPG
                    )
                    return
                elif screenshot_bytes.startswith(b'\x89PNG'):
                    # PNG画像
                    allure.attach(
                        screenshot_bytes,
                        name=f"Screenshot - {context}",
                        attachment_type=allure.attachment_type.PNG
                    )
                    return
                else:
                    allure.attach(
                        f"Invalid image data (first 20 bytes): {screenshot_bytes[:20]}",
                        name=f"Screenshot Invalid Data - {context}",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    return
                    
            except Exception as e:
                allure.attach(
                    f"Failed to decode base64: {str(e)}",
                    name=f"Screenshot Decode Error - {context}",
                    attachment_type=allure.attachment_type.TEXT
                )
                return
        
        # mobile-mcpのレスポンス構造に基づく処理
        if screenshot_result and hasattr(screenshot_result, 'content'):
            content = screenshot_result.content
            
            # mobile-mcpは content: [{ type: "image", data: base64_string, mimeType: "image/png" }] を返す
            if isinstance(content, list) and len(content) > 0:
                image_content = content[0]
                if isinstance(image_content, dict) and image_content.get('type') == 'image':
                    screenshot_data = image_content.get('data')
                    mime_type = image_content.get('mimeType', 'image/png')
                    
                    if screenshot_data:
                        # Base64デコード
                        import base64
                        screenshot_bytes = base64.b64decode(screenshot_data)
                        
                        # MIMEタイプに基づいてAllure添付タイプを決定
                        if mime_type == 'image/jpeg':
                            attachment_type = allure.attachment_type.JPG
                        else:
                            attachment_type = allure.attachment_type.PNG
                        
                        allure.attach(
                            screenshot_bytes,
                            name=f"Screenshot - {context}",
                            attachment_type=attachment_type
                        )
                        return
                        
                    else:
                        allure.attach(
                            f"No image data in content: {image_content}",
                            name=f"Screenshot No Data - {context}",
                            attachment_type=allure.attachment_type.TEXT
                        )
                else:
                    allure.attach(
                        f"Unexpected content format: {content}",
                        name=f"Screenshot Format Error - {context}",
                        attachment_type=allure.attachment_type.TEXT
                    )
            else:
                allure.attach(
                    f"Content is not a list or empty: {content}",
                    name=f"Screenshot Content Error - {context}",
                    attachment_type=allure.attachment_type.TEXT
                )
        else:
            allure.attach(
                f"No content in response: {screenshot_result}",
                name=f"Screenshot Response Error - {context}",
                attachment_type=allure.attachment_type.TEXT
            )
                        
    except Exception as e:
        allure.attach(
            f"Failed to capture mobile screenshot: {str(e)}",
            name=f"Screenshot Error - {context}",
            attachment_type=allure.attachment_type.TEXT
        )


class AndroidBaseTest:
    """
    Android テスト用の基底クラス
    
    共通的なアサーションメソッドやヘルパー関数を提供
    """
    
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


# --- Android版エージェントステップ記録機能 ---

async def record_android_step(agent):
    """
    Android エージェントの各ステップを記録する関数
    
    Web版のrecord_step機能をAndroid版に移植。
    エージェントの各アクション終了時にスクリーンショット、Thoughts、実行時間等を記録。
    
    Args:
        agent: AndroidBaseAgentTestインスタンス
    """
    if not agent or not hasattr(agent, 'conversation_history'):
        return

    # 最新の会話履歴から情報を取得
    if not agent.conversation_history:
        return
    
    last_conversation = agent.conversation_history[-1]
    action_task = last_conversation.get('task', 'Unknown Action')
    action_result = last_conversation.get('result', 'No result')
    
    # ステップタイトルを生成（Web版と同様の形式）
    step_title = f"Mobile Action: {action_task[:50]}..."
    
    with allure.step(step_title):
        # Agent Thoughts を添付（結果から推論プロセスを抽出）
        try:
            thoughts_content = _extract_agent_thoughts(action_task, action_result)
            if thoughts_content:
                allure.attach(
                    thoughts_content,
                    name="Agent Thoughts",
                    attachment_type=allure.attachment_type.TEXT,
                )
        except Exception as e:
            allure.attach(
                f"Failed to extract agent thoughts: {str(e)}",
                name="Thoughts Extraction Error",
                attachment_type=allure.attachment_type.TEXT,
            )

        # デバイス情報を添付
        device_id = agent._current_device_id or "emulator-5554"
        allure.attach(
            f"Device: {device_id}",
            name="Device Info",
            attachment_type=allure.attachment_type.TEXT,
        )

        # 現在のアプリ情報を添付
        if agent._current_app_bundle_id:
            allure.attach(
                agent._current_app_bundle_id,
                name="Current App",
                attachment_type=allure.attachment_type.TEXT,
            )

        # ステップ実行時間を添付
        timestamp = last_conversation.get('timestamp')
        if timestamp:
            import time
            duration = time.time() - timestamp
            allure.attach(
                f"{duration:.2f}s",
                name="Step Duration",
                attachment_type=allure.attachment_type.TEXT,
            )

        # スクリーンショットを添付（アクション終了後の状態）
        try:
            await _capture_mobile_screenshot(agent, f"After Action: {action_task[:30]}...")
        except Exception as e:
            allure.attach(
                f"Failed to capture screenshot: {str(e)}",
                name="Screenshot Error",
                attachment_type=allure.attachment_type.TEXT,
            )


def _extract_agent_thoughts(task: str, result: str) -> str:
    """
    エージェントのタスクと結果から思考プロセスを抽出
    
    Args:
        task: 実行されたタスク
        result: エージェントの実行結果
        
    Returns:
        抽出された思考プロセスの文字列
    """
    thoughts_lines = []
    
    # タスク分析
    thoughts_lines.append(f"🎯 Task Analysis: {task}")
    thoughts_lines.append("")
    
    # タスクからの意図推論
    task_lower = task.lower()
    if "screenshot" in task_lower:
        thoughts_lines.append("💭 Intent: Capture current screen state for verification")
    elif "click" in task_lower or "tap" in task_lower:
        thoughts_lines.append("💭 Intent: Interact with UI element through touch gesture")
    elif "type" in task_lower or "input" in task_lower:
        thoughts_lines.append("💭 Intent: Provide text input to form or search field")
    elif "launch" in task_lower or "open" in task_lower:
        thoughts_lines.append("💭 Intent: Start target application for test execution")
    elif "navigate" in task_lower or "go to" in task_lower:
        thoughts_lines.append("💭 Intent: Navigate to specific location or feature")
    elif "scroll" in task_lower:
        thoughts_lines.append("💭 Intent: Scroll to reveal additional content or elements")
    elif "search" in task_lower:
        thoughts_lines.append("💭 Intent: Find specific content or information")
    else:
        thoughts_lines.append("💭 Intent: Execute mobile automation operation")
    
    thoughts_lines.append("")
    
    # 結果から実行されたアクションを推論
    result_lower = result.lower()
    
    if "screenshot" in result_lower or "image" in result_lower:
        thoughts_lines.append("🔧 Action Taken: Screenshot captured successfully")
        if "failed" not in result_lower:
            thoughts_lines.append("✅ Reasoning: Visual state documented for analysis")
    elif "click" in result_lower or "tap" in result_lower:
        thoughts_lines.append("🔧 Action Taken: Touch interaction performed")
        if "coordinates" in result_lower:
            thoughts_lines.append("✅ Reasoning: Used coordinate-based click for precise targeting")
        else:
            thoughts_lines.append("✅ Reasoning: Element-based interaction executed")
    elif "type" in result_lower or "input" in result_lower:
        thoughts_lines.append("🔧 Action Taken: Text input completed")
        thoughts_lines.append("✅ Reasoning: Data entry successful for form interaction")
    elif "launch" in result_lower or "open" in result_lower:
        thoughts_lines.append("🔧 Action Taken: Application launched")
        thoughts_lines.append("✅ Reasoning: Target app started and ready for interaction")
    elif "scroll" in result_lower:
        thoughts_lines.append("🔧 Action Taken: Scroll operation executed")
        thoughts_lines.append("✅ Reasoning: Content area adjusted to reveal target elements")
    elif "navigate" in result_lower or "go to" in result_lower:
        thoughts_lines.append("🔧 Action Taken: Navigation completed")
        thoughts_lines.append("✅ Reasoning: Successfully moved to target screen/location")
    elif "search" in result_lower:
        thoughts_lines.append("🔧 Action Taken: Search operation performed")
        thoughts_lines.append("✅ Reasoning: Query executed to find relevant content")
    elif "error" in result_lower or "failed" in result_lower:
        thoughts_lines.append("❌ Action Taken: Operation encountered error")
        thoughts_lines.append("🔍 Reasoning: Alternative approach may be needed")
    else:
        thoughts_lines.append("🔧 Action Taken: General mobile automation task executed")
        thoughts_lines.append("✅ Reasoning: Standard operation completed")
    
    thoughts_lines.append("")
    
    # 結果の品質評価
    if len(result.strip()) > 100:
        thoughts_lines.append("📊 Result Quality: Detailed response received")
    elif len(result.strip()) > 20:
        thoughts_lines.append("📊 Result Quality: Adequate response length")
    else:
        thoughts_lines.append("⚠️ Result Quality: Brief response - may need verification")
    
    thoughts_lines.append("")
    
    # 結果サマリ（長すぎる場合は切り詰め）
    result_summary = result[:300] + "..." if len(result) > 300 else result
    thoughts_lines.append("📝 Execution Result Summary:")
    thoughts_lines.append(f"   {result_summary}")
    
    return "\n".join(thoughts_lines)


# Allure報告用のカスタムステップデコレータ
def allure_android_step(step_description: str):
    """
    Android特有のステップ用Allureデコレータ
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with allure.step(f"📱 {step_description}"):
                return await func(*args, **kwargs)
        return wrapper
    return decorator
