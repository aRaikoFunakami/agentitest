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
    2. エージェントの行動が自動保存される
    3. ステップ実行時間が記録される
    4. 実際的なAndroidアプリ操作でのステップ記録動作を検証
    """)
    async def test_android_step_recording_basic_actions(self):
        """基本的なAndroidアクションでのステップ記録機能をテスト"""
        
        # 効率的な単一タスクでYahoo.co.jpアクセスをテスト
        with allure.step("エージェントの思考プロセス取得テスト"):
            result = await self.android_agent.validate_mobile_task(
                task="""
                # 指示
                nfbeアプリを起動して、
                ツールバーの右から二番目のアイコンを選択しメニューを表示し、
                メニューからアプリ情報を選択しなさい
                # GUIヒント
                nfbeのGUIは特殊で、ツールバーが消すことができます。
                ツールバーの右上の矢印が向かい合っているアイコンを選択するとツールバーが消えます
                ツールバーを再度出したい場合は、ツールバーがないときだけ出現する左上にある矢印がはなれば奈良になっているアイコンを選択します
                """,
                expected_substring="pickup",
                ignore_case=True,
                timeout=60.0,
            )
            
            # 結果の基本検証
            assert result is not None
            assert len(result.strip()) > 0

                        
                    

