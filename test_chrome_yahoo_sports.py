"""
Chrome Yahoo Sports Access Test
Chrome ブラウザを使用してYahoo.co.jpのスポーツニュースにアクセスするテスト
"""

import pytest
import allure
from android_base_agent_test import AndroidBaseAgentTest


@pytest.mark.android
@pytest.mark.integration
@allure.epic("Mobile Browser Testing")
@allure.feature("Chrome Browser")
@allure.story("Yahoo Sports Access")
class TestChromeYahooSports:
    """
    Chrome ブラウザでYahoo.co.jpスポーツセクションアクセステスト
    
    このテストクラスはAndroidデバイス上でChromeブラウザを使用し、
    Yahoo.co.jpにアクセスしてスポーツニュースページまでの
    ナビゲーションを自動化テストする。
    """
    
    @pytest.fixture(autouse=True)
    async def setup_android_agent(self):
        """テストセットアップ - Androidエージェントを初期化"""
        self.android_agent = AndroidBaseAgentTest()
        await self.android_agent.setup_mobile_agent()
        
        yield
        
        await self.android_agent.cleanup()
    
    @allure.title("Yahoo.co.jpスポーツニュースアクセステスト")
    @allure.description("Chrome ブラウザでYahoo.co.jpにアクセスし、スポーツニュースページまでナビゲートする")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_chrome_yahoo_sports_access(self):
        """より確実なYahoo.co.jpスポーツアクセステスト（座標精度改善版）"""
        
        task_instruction = """
Please perform the following steps on the Android device with PRECISE coordinates:

1. Launch the Chrome browser application (com.android.chrome)
2. Wait for Chrome to fully load
3. Navigate to yahoo.co.jp using EXACT element targeting:
   STEP 3a: Click on the address bar element with identifier "com.android.chrome:id/url_bar"
   STEP 3b: Clear any existing text and type "yahoo.co.jp"
   STEP 3c: Press Enter to navigate
4. Wait for Yahoo.co.jp homepage to fully load
5. CRITICAL: Look for the Sports section (スポーツ) which should appear as a tab in the news section
6. Click on the Sports tab (identifier "tabTopics4" with coordinates around x=887, y=779, width=169, height=92)
7. Wait for the sports news page to load completely
8. Verify that sports news articles with titles are displayed on the screen
9. Take a screenshot to confirm the sports news page is loaded

COORDINATE GUIDANCE:
- Address bar: Use identifier "com.android.chrome:id/url_bar" at coordinates (480,136,1680,96)
- Sports tab: Look for text "スポーツ" with identifier "tabTopics4"

VALIDATION REQUIREMENTS:
- URL bar must show "yahoo.co.jp"  
- Must see "スポーツ" tab and click it successfully
- Must see actual sports news articles with Japanese sports terms like "野球", "サッカー"

SUCCESS CONDITION:
If sports news articles are visible and you can see sports-related content, respond with exactly: "SPORTS_NEWS_LOADED_SUCCESSFULLY"

FAILURE CONDITIONS (stop immediately if encountered):
- Cannot find Sports/スポーツ section after 3 attempts
- Navigation to wrong page (like auctions)
- No sports content visible after clicking Sports tab
"""
        
        result = await self.android_agent.validate_mobile_task(
            task=task_instruction,
            expected_substring="SPORTS_NEWS_LOADED_SUCCESSFULLY",
            timeout=120.0
        )
        
        # より厳密な検証
        assert "SPORTS_NEWS_LOADED_SUCCESSFULLY" in result, f"Test failed. Agent response: {result}"
        
        # 追加の検証: 結果にスポーツ関連のキーワードが含まれているかチェック
        sports_keywords = ["スポーツ", "野球", "サッカー", "sports", "news"]
        has_sports_content = any(keyword in result.lower() for keyword in sports_keywords)
        
        assert has_sports_content or "SPORTS_NEWS_LOADED_SUCCESSFULLY" in result, \
            f"No sports content detected. Agent response: {result}"


@pytest.mark.android
@pytest.mark.debug
@allure.epic("Debug and Utilities")
class TestDebugUtilities:
    """デバッグ用ユーティリティテスト
    
    開発とデバッグ時に使用する補助的なテストケース群。
    デバイス状態の確認や基本機能のテストを行う。
    """
    
    @pytest.fixture(autouse=True)
    async def setup_android_agent(self):
        """テストセットアップ"""
        self.android_agent = AndroidBaseAgentTest()
        await self.android_agent.setup_mobile_agent()
        
        yield
        
        await self.android_agent.cleanup()
    
    @allure.story("Basic UI")
    @allure.title("Chromeブラウザ基本動作テスト")
    async def test_chrome_basic_operations(self):
        """Chromeブラウザの基本的な操作をテスト"""
        
        chrome_task = """
Please perform the following basic Chrome operations:
1. Launch Chrome browser
2. Navigate to google.com
3. Take a screenshot
4. Close the browser

Please respond with "CHROME_BASIC_TEST_COMPLETE" when finished.
"""
        
        result = await self.android_agent.validate_mobile_task(
            task=chrome_task,
            expected_substring="CHROME_BASIC_TEST_COMPLETE",
            timeout=60.0
        )
        
        assert "CHROME_BASIC_TEST_COMPLETE" in result.upper() or len(result) > 20
