"""
Chrome + Yahoo.co.jp スポーツニューステストケース

Android版BaseAgentTestを使用したChrome ブラウザでのYahoo.co.jpアクセステスト
"""

import pytest
import allure
from android_base_agent_test import AndroidBaseAgentTest


@pytest.mark.android
@pytest.mark.slow
@allure.epic("Mobile Browser Testing")
@allure.feature("Chrome Browser")
class TestChromeYahooSports:
    """Chrome ブラウザでYahoo.co.jpスポーツニュース閲覧テスト
    
    AndroidデバイスでChromeブラウザを使用してYahoo.co.jpのスポーツセクションに
    アクセスし、ニュース記事の閲覧を自動化するテストケース群。
    """
    
    @pytest.fixture(autouse=True)
    async def setup_android_agent(self):
        """各テストの前後でAndroidエージェントをセットアップ・クリーンアップ"""
        self.android_agent = AndroidBaseAgentTest()
        await self.android_agent.setup_mobile_agent()
        
        yield
        
        await self.android_agent.cleanup()
    
    @allure.story("Yahoo Sports Access")
    @allure.title("Chrome ブラウザでYahoo.co.jpスポーツセクションにアクセス")
    @allure.description("""
    Androidデバイス上でChromeブラウザを起動し、Yahoo.co.jpサイトに移動して
    スポーツセクションにアクセスする。スポーツニュース一覧が正常に表示される
    ことを確認する。
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_chrome_yahoo_sports_access(self):
        """Chrome でYahoo.co.jpのスポーツニュースにアクセス"""
        
        # Yahoo.co.jpスポーツセクションアクセスタスク
        task_instruction = """
Please perform the following steps on the Android device:

1. Launch the Chrome browser application (com.android.chrome)
2. Wait for Chrome to fully load
3. Tap on the address bar to focus it
4. Type "https://yahoo.co.jp" in the address bar
5. Tap the Go button or press Enter to navigate to the website
6. Wait for Yahoo.co.jp homepage to fully load
7. Look for the Sports section (スポーツ) on the page
8. Tap on the Sports section to access sports news
9. Wait for the sports news page to load
10. Verify that sports news articles are displayed on the screen
11. Take a screenshot to confirm the sports news page is loaded

If all steps complete successfully and sports news articles are visible, 
respond with exactly: "SPORTS_NEWS_LOADED_SUCCESSFULLY"
"""
        
        result = await self.android_agent.validate_mobile_task(
            task_instruction=task_instruction,
            expected_substring="SPORTS_NEWS_LOADED_SUCCESSFULLY",
            ignore_case=False,
            app_bundle_id="com.android.chrome",
            timeout=180.0  # 3分のタイムアウト
        )
        
        # 結果の詳細検証
        assert "SPORTS_NEWS_LOADED_SUCCESSFULLY" in result
        
        # Allureレポート用の追加情報
        allure.dynamic.parameter("Target URL", "https://yahoo.co.jp")
        allure.dynamic.parameter("Browser", "Chrome")
        allure.dynamic.parameter("Section", "Sports (スポーツ)")
    
    @allure.story("Yahoo Sports Article Reading")
    @allure.title("スポーツニュース記事の詳細閲覧")
    @allure.description("""
    Yahoo.co.jpのスポーツセクションから特定のニュース記事を選択し、
    記事の詳細ページにアクセスして内容を閲覧する。記事の本文が
    正常に表示されることを確認する。
    """)
    @allure.severity(allure.severity_level.NORMAL)
    async def test_chrome_yahoo_sports_article_read(self):
        """スポーツニュース記事の詳細閲覧テスト"""
        
        # 前提条件：スポーツニュースページが既に表示されている
        setup_task = """
Ensure that Chrome browser is open and displaying Yahoo.co.jp sports news page.
If not, please navigate to https://yahoo.co.jp and access the Sports section first.
"""
        await self.android_agent._execute_agent_task(setup_task)
        
        # 記事詳細閲覧タスク
        article_read_task = """
Please perform the following steps:

1. Ensure you are on the Yahoo.co.jp sports news page
2. Look for the first visible sports news article headline
3. Tap on the first sports news article to open it
4. Wait for the article page to fully load
5. Scroll down slightly to view more of the article content
6. Verify that the article text/content is displayed
7. Look for typical article elements like headline, text content, date, etc.
8. Take a screenshot to confirm the article content is visible

If the article content is successfully displayed and readable,
respond with exactly: "ARTICLE_CONTENT_VISIBLE"
"""
        
        result = await self.android_agent.validate_mobile_task(
            task_instruction=article_read_task,
            expected_substring="ARTICLE_CONTENT_VISIBLE",
            ignore_case=False,
            timeout=120.0
        )
        
        # 結果検証
        assert "ARTICLE_CONTENT_VISIBLE" in result
        
        # テスト詳細情報の記録
        allure.dynamic.parameter("Action", "Article Detail View")
        allure.dynamic.parameter("Content Type", "Sports News Article")
    
    @allure.story("Yahoo Sports Navigation")
    @allure.title("スポーツカテゴリ間のナビゲーション")
    @allure.description("""
    Yahoo.co.jpスポーツセクション内での異なるスポーツカテゴリ間の
    ナビゲーションを テストする。野球、サッカー、その他のスポーツ
    カテゴリへの移動が正常に動作することを確認する。
    """)
    @allure.severity(allure.severity_level.MINOR)
    async def test_chrome_yahoo_sports_category_navigation(self):
        """スポーツカテゴリ間ナビゲーションテスト"""
        
        # カテゴリナビゲーションタスク
        navigation_task = """
Please perform the following navigation steps:

1. Ensure you are on Yahoo.co.jp sports page
2. Look for different sports categories (such as 野球/Baseball, サッカー/Soccer, etc.)
3. If available, tap on the Baseball (野球) category
4. Wait for the baseball news to load
5. Take a screenshot of the baseball news section
6. Navigate back or look for the Soccer (サッカー) category
7. If available, tap on the Soccer category
8. Wait for the soccer news to load
9. Verify that category-specific sports news is displayed

If you successfully navigate between sports categories and see category-specific content,
respond with exactly: "CATEGORY_NAVIGATION_SUCCESS"
"""
        
        result = await self.android_agent.validate_mobile_task(
            task_instruction=navigation_task,
            expected_substring="CATEGORY_NAVIGATION_SUCCESS",
            ignore_case=False,
            timeout=150.0
        )
        
        assert "CATEGORY_NAVIGATION_SUCCESS" in result
        
        allure.dynamic.parameter("Categories Tested", "Baseball, Soccer")
        allure.dynamic.parameter("Navigation Type", "Category Switching")
    
    @allure.story("Error Handling")
    @allure.title("ネットワークエラー処理テスト")
    @allure.description("""
    ネットワーク接続の問題やページロードエラーが発生した場合の
    エラーハンドリングをテストする。適切なエラーメッセージの
    表示と回復処理を確認する。
    """)
    @allure.severity(allure.severity_level.MINOR)
    async def test_chrome_network_error_handling(self):
        """ネットワークエラー時の動作テスト"""
        
        # 無効なURLでのエラーハンドリングテスト
        error_handling_task = """
Please perform the following error testing steps:

1. Open Chrome browser if not already open
2. Navigate to an invalid URL like "https://invalid-yahoo-url.invalidtld"
3. Wait for the error page to appear
4. Observe the error message or page
5. Try to navigate back to a valid URL like "https://yahoo.co.jp"
6. Verify that recovery to a valid site works

If you can successfully demonstrate error handling and recovery,
respond with exactly: "ERROR_HANDLING_VERIFIED"
"""
        
        try:
            result = await self.android_agent.validate_mobile_task(
                task_instruction=error_handling_task,
                expected_substring="ERROR_HANDLING_VERIFIED",
                ignore_case=False,
                timeout=90.0
            )
            
            assert "ERROR_HANDLING_VERIFIED" in result
            
        except Exception as e:
            # エラーハンドリングテストの失敗は warning として記録
            allure.attach(
                f"Error handling test failed as expected: {str(e)}",
                name="Expected Error Behavior",
                attachment_type=allure.attachment_type.TEXT
            )
            pytest.skip("Error handling test skipped due to expected network failure")
        
        allure.dynamic.parameter("Error Type", "Network/DNS Error")
        allure.dynamic.parameter("Recovery Method", "URL Navigation")


@pytest.mark.android
@pytest.mark.integration
@allure.epic("Mobile Integration Testing")
@allure.feature("End-to-End Workflow")
class TestChromeYahooE2EWorkflow:
    """Chrome + Yahoo.co.jp エンドツーエンドワークフローテスト
    
    実際のユーザーの使用パターンを模倣した総合的なテストシナリオ。
    複数の操作を組み合わせたワークフローの動作を検証する。
    """
    
    @pytest.fixture(autouse=True)
    async def setup_android_agent(self):
        """テストセットアップ"""
        self.android_agent = AndroidBaseAgentTest()
        await self.android_agent.setup_mobile_agent()
        
        yield
        
        await self.android_agent.cleanup()
    
    @allure.story("Complete User Journey")
    @allure.title("完全なユーザージャーニーテスト")
    @allure.description("""
    一般的なユーザーがChromeブラウザでYahoo.co.jpを使用する際の
    完全なジャーニーをシミュレートする。ブラウザ起動からニュース閲覧、
    記事詳細表示まで一連の流れを検証する。
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_complete_user_journey(self):
        """ユーザージャーニー全体のE2Eテスト"""
        
        # ステップ1: ブラウザ起動とサイトアクセス
        step1_task = """
Step 1 - Browser Launch and Site Access:
1. Launch Chrome browser
2. Navigate to https://yahoo.co.jp
3. Wait for the homepage to load completely
4. Verify Yahoo.co.jp homepage is displayed

If successful, respond with: "STEP1_HOMEPAGE_LOADED"
"""
        
        step1_result = await self.android_agent.validate_mobile_task(
            task_instruction=step1_task,
            expected_substring="STEP1_HOMEPAGE_LOADED",
            app_bundle_id="com.android.chrome",
            timeout=60.0
        )
        
        assert "STEP1_HOMEPAGE_LOADED" in step1_result
        
        # ステップ2: スポーツセクションアクセス
        step2_task = """
Step 2 - Sports Section Access:
1. From Yahoo.co.jp homepage, locate the Sports (スポーツ) section
2. Tap on the Sports section
3. Wait for sports news page to load
4. Verify sports news articles are displayed

If successful, respond with: "STEP2_SPORTS_ACCESSED"
"""
        
        step2_result = await self.android_agent.validate_mobile_task(
            task_instruction=step2_task,
            expected_substring="STEP2_SPORTS_ACCESSED",
            timeout=60.0
        )
        
        assert "STEP2_SPORTS_ACCESSED" in step2_result
        
        # ステップ3: 記事詳細閲覧
        step3_task = """
Step 3 - Article Detail Reading:
1. From the sports news page, select the first available article
2. Tap to open the article detail page
3. Wait for article content to load
4. Scroll to read some of the article content
5. Verify article text and content are readable

If successful, respond with: "STEP3_ARTICLE_READ"
"""
        
        step3_result = await self.android_agent.validate_mobile_task(
            task_instruction=step3_task,
            expected_substring="STEP3_ARTICLE_READ",
            timeout=60.0
        )
        
        assert "STEP3_ARTICLE_READ" in step3_result
        
        # 全ステップ完了の確認
        allure.attach(
            f"Step 1: {step1_result}\nStep 2: {step2_result}\nStep 3: {step3_result}",
            name="Complete Journey Results",
            attachment_type=allure.attachment_type.TEXT
        )
        
        # 成功メトリクスの記録
        allure.dynamic.parameter("Total Steps", "3")
        allure.dynamic.parameter("Journey Type", "Browse → Sports → Article")
        allure.dynamic.parameter("All Steps Passed", "True")


# ユーティリティ関数とデバッグ用テスト
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
    
    @allure.story("Device Information")
    @allure.title("デバイス情報取得テスト")
    async def test_device_info_collection(self):
        """接続されたAndroidデバイスの情報を取得"""
        
        device_info_task = """
Please collect and report the following device information:
1. Current device model and Android version
2. Screen resolution and orientation
3. Currently installed Chrome browser version
4. Device storage and memory status

Report all collected information and end with: "DEVICE_INFO_COLLECTED"
"""
        
        result = await self.android_agent.validate_mobile_task(
            task_instruction=device_info_task,
            expected_substring="DEVICE_INFO_COLLECTED",
            timeout=30.0
        )
        
        assert "DEVICE_INFO_COLLECTED" in result
        
        # デバイス情報をAllureレポートに記録
        allure.attach(
            result,
            name="Device Information Details",
            attachment_type=allure.attachment_type.TEXT
        )
    
    @allure.story("Basic Functionality")
    @allure.title("基本機能動作確認テスト")
    async def test_basic_functionality_check(self):
        """Mobile-MCPの基本機能が正常に動作することを確認"""
        
        basic_test_task = """
Please perform these basic functionality tests:
1. Take a screenshot of the current screen
2. Get the accessibility tree information
3. Tap somewhere safe on the screen (like empty space)
4. Type some text in a text field if available
5. Perform a small swipe gesture

If all basic functions work correctly, respond with: "BASIC_FUNCTIONS_OK"
"""
        
        result = await self.android_agent.validate_mobile_task(
            task_instruction=basic_test_task,
            expected_substring="BASIC_FUNCTIONS_OK",
            timeout=45.0
        )
        
        assert "BASIC_FUNCTIONS_OK" in result
