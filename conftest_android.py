"""
Android版conftest.py

Mobile-MCPを使用したAndroidテスト用のpytest設定ファイル
"""

import asyncio
import logging
import os
import sys
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
        # スクリーンショット取得
        await agent._attach_current_screenshot(f"Test Failure: {test_name}")
        
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
