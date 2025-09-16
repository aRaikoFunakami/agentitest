"""
スクリーンショット機能の単体テスト
"""
import asyncio
import pytest
import allure
from android_base_agent_test import AndroidBaseAgentTest


class TestScreenshotDebug:
    """スクリーンショット機能のデバッグテスト"""
    
    @pytest.fixture(autouse=True)
    async def setup_agent(self):
        """テスト用のエージェントセットアップ"""
        self.android_agent = AndroidBaseAgentTest()
        await self.android_agent.setup_mobile_agent()
        yield
        await self.android_agent.cleanup()
    
    @allure.title("スクリーンショット直接呼び出しテスト")
    async def test_direct_screenshot_call(self):
        """_attach_current_screenshotメソッドを直接呼び出してテスト"""
        
        # Chrome起動
        print("Step 1: Launching Chrome...")
        await self.android_agent._launch_application("com.android.chrome")
        
        # 1秒待機してアプリが完全に起動するまで待つ
        await asyncio.sleep(1)
        
        # スクリーンショット直接呼び出し
        print("Step 2: Taking screenshot...")
        await self.android_agent._attach_current_screenshot("Direct Test Screenshot")
        
        print("Step 3: Screenshot test completed")
        
        # 基本的なアサーション
        assert self.android_agent._current_device_id is not None
        assert self.android_agent._current_app_bundle_id == "com.android.chrome"
    
    @allure.title("mobile_save_screenshotツール直接呼び出しテスト")
    async def test_mobile_save_screenshot_tool(self):
        """mobile_save_screenshotツールを直接呼び出してテスト"""
        
        print("Step 1: Getting MCP tools...")
        mobile_tools = await self.android_agent.mcp_client.get_tools()
        screenshot_tool = None
        
        for tool in mobile_tools:
            if hasattr(tool, 'name') and tool.name == 'mobile_save_screenshot':
                screenshot_tool = tool
                break
        
        assert screenshot_tool is not None, "mobile_save_screenshot tool not found"
        
        print("Step 2: Calling mobile_save_screenshot...")
        result = await screenshot_tool.ainvoke({"device": "emulator-5554"})
        
        print(f"Screenshot result: {result}")
        print(f"Result type: {type(result)}")
        
        # 結果をAllureに添付
        allure.attach(
            f"Screenshot tool result: {result}",
            name="Screenshot Tool Result",
            attachment_type=allure.attachment_type.TEXT
        )
        
        # 基本的なアサーション
        assert result is not None
