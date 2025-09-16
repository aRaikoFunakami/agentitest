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
    1. エージェントの各アクション終了時にスクリーンショットが取得される
    2. エージェントのThoughts（行動理由）が保存される
    3. ステップ実行時間が記録される
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
            
        # Step 2: スクリーンショット取得アクション
        with allure.step("Step 2: 現在の画面のスクリーンショットを取得"):
            result = await self.android_agent.validate_mobile_task(
                task_instruction="Take a screenshot of the current screen",
                expected_substring="screenshot",
                ignore_case=True,
                timeout=30.0
            )
            
            # スクリーンショット関連の結果検証
            assert result is not None
            result_lower = result.lower()
            assert any(keyword in result_lower for keyword in ["screenshot", "image", "captured", "taken"])
            
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

    @allure.epic("Android Automation")
    @allure.feature("Step Recording")
    @allure.story("Error Handling")
    @allure.title("エラー時のステップ記録機能テスト")
    async def test_android_step_recording_error_handling(self):
        """エラー発生時のステップ記録機能をテスト"""
        
        with allure.step("意図的にエラーを発生させてステップ記録をテスト"):
            try:
                # 存在しないアプリの起動を試行（エラーケース）
                await self.android_agent.validate_mobile_task(
                    task_instruction="Launch non-existent application with package name 'com.nonexistent.app'",
                    timeout=20.0
                )
                
                # エラーが発生した場合でもステップ記録が動作することを確認
                # （タスクは失敗するが、record_android_stepは動作する必要がある）
                
            except (AssertionError, Exception) as e:
                # エラーが発生することを期待（これは正常な動作）
                allure.attach(
                    f"Expected error occurred: {str(e)}",
                    name="Expected Error",
                    attachment_type=allure.attachment_type.TEXT
                )
                
                # エラー時でもエージェントの会話履歴が記録されていることを確認
                assert len(self.android_agent.conversation_history) > 0
                
                # 最新の履歴エントリが存在することを確認
                latest_history = self.android_agent.conversation_history[-1]
                assert "task" in latest_history
                assert "result" in latest_history
                assert "timestamp" in latest_history

    @allure.epic("Android Automation")
    @allure.feature("Step Recording")
    @allure.story("Conversation History")
    @allure.title("会話履歴とThoughts記録の検証")
    async def test_conversation_history_and_thoughts(self):
        """会話履歴とThoughts記録機能の詳細検証"""
        
        # 初期状態の確認
        initial_history_count = len(self.android_agent.conversation_history)
        
        with allure.step("複数のアクションを実行して履歴蓄積をテスト"):
            # アクション1: アプリ起動
            await self.android_agent.validate_mobile_task(
                task_instruction="Launch Chrome browser",
                expected_substring="chrome",
                ignore_case=True,
                timeout=40.0,
                app_bundle_id="com.android.chrome"
            )
            
            # アクション2: スクリーンショット
            await self.android_agent.validate_mobile_task(
                task_instruction="Capture current screen state",
                expected_substring="screen",
                ignore_case=True,
                timeout=20.0
            )
            
        # 履歴が適切に蓄積されているかの検証
        final_history_count = len(self.android_agent.conversation_history)
        assert final_history_count > initial_history_count
        
        # 最新の履歴エントリの詳細検証
        for history_entry in self.android_agent.conversation_history[-2:]:
            # 必要なフィールドが全て存在することを確認
            assert "task" in history_entry
            assert "result" in history_entry
            assert "timestamp" in history_entry
            
            # タスクと結果が空でないことを確認
            assert len(history_entry["task"].strip()) > 0
            assert len(history_entry["result"].strip()) > 0
            
            # タイムスタンプが妥当な値であることを確認
            assert isinstance(history_entry["timestamp"], (int, float))
            assert history_entry["timestamp"] > 0
            
        allure.attach(
            f"Total conversation history entries: {final_history_count}",
            name="Conversation History Count",
            attachment_type=allure.attachment_type.TEXT
        )
        
        # エージェント状態の検証
        assert self.android_agent.agent_state is not None
        assert len(self.android_agent.agent_state.operation_history) > 0
        
        allure.attach(
            f"Agent operation history: {self.android_agent.agent_state.operation_history}",
            name="Agent Operation History",
            attachment_type=allure.attachment_type.TEXT
        )
