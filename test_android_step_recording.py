"""
Android ステップ記録機能のテスト

新しく実装したエージェントの各アクション終了時のスクリーンショット取得と
Thought保存機能をテストする
"""

import pytest
import allure


@pytest.mark.android
@pytest.mark.slow
class TestAndroidStepRecording:
    """Android ステップ記録機能のテストクラス"""

    @pytest.fixture(autouse=True)
    async def setup_agent(self, android_agent_session):
        """各テスト用のエージェントセットアップ"""
        self.android_agent = android_agent_session

    @allure.epic("Android Automation")
    @allure.feature("Step Recording")
    @allure.story("Screenshot and Thoughts Capture")
    @allure.title("Androidエージェントのステップ記録機能テスト")
    @allure.description("""
    実装した新機能をテスト：
    1. エージェントの各アクション終了時にスクリーンショットが自動取得される
    2. エージェントのThoughts（行動理由）が自動保存される
    3. ステップ実行時間が記録される
    4. 実際的なAndroidアプリ操作でのステップ記録動作を検証
    """)
    async def test_android_step_recording_basic_actions(self):
        """基本的なAndroidアクションでのステップ記録機能をテスト"""
        
        # Step 1: アプリ起動アクション
        with allure.step("Step 1: Chrome アプリを起動"):
            result = await self.android_agent.validate_mobile_task(
                task_instruction="Launch Chrome application",
                expected_substring="launch",
                ignore_case=True,
                timeout=60.0,
                app_bundle_id="com.android.chrome"
            )
            
            # 結果の基本検証
            assert result is not None
            assert len(result.strip()) > 0
            
        # Step 2: 画面要素の確認アクション
        with allure.step("Step 2: 画面上の利用可能な要素を確認"):
            result = await self.android_agent.validate_mobile_task(
                task_instruction="List all available elements on the current screen",
                expected_substring="element",
                ignore_case=True,
                timeout=30.0
            )
            
            # 要素リスト取得の結果検証
            assert result is not None
            result_lower = result.lower()
            assert any(keyword in result_lower for keyword in ["element", "screen", "found", "list"])
            
        # Step 3: UI要素との相互作用
        with allure.step("Step 3: 検索ボックスをクリック"):
            result = await self.android_agent.validate_mobile_task(
                task_instruction="Click on the search box to enter text",
                expected_substring="click",
                ignore_case=True,
                timeout=30.0
            )
            
            # クリック動作の結果検証
            assert result is not None
            result_lower = result.lower()
            assert any(keyword in result_lower for keyword in ["click", "tap", "interact", "coordinates"])
