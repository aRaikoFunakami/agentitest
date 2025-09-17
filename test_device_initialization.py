import pytest
from android_base_agent_test import AndroidBaseAgentTest

class TestDeviceInitialization:
    """デバイス初期化機能のテストクラス"""
    
    @pytest.mark.asyncio
    async def test_device_initialization_flow(self):
        """デバイス初期化フローのテスト"""
        test_instance = AndroidBaseAgentTest()
        
        # MCP サーバーの初期化
        try:
            await test_instance._initialize_mcp_servers()
            print("✅ MCP servers initialized successfully")
        except Exception as e:
            print(f"❌ MCP initialization failed: {e}")
            raise
        
        # デバイス ID の初期化
        try:
            device_id = await test_instance._initialize_device_id()
            print(f"✅ Device ID initialized: {device_id}")
            assert device_id is not None
            assert isinstance(device_id, str)
            assert len(device_id) > 0
        except Exception as e:
            print(f"❌ Device ID initialization failed: {e}")
            # デバイス検出エラーでもテストは続行（デフォルトIDが設定されるため）
            assert test_instance.device_id is not None
            print(f"✅ Fallback device ID used: {test_instance.device_id}")
        
        # React エージェントの初期化
        try:
            await test_instance._initialize_react_agent()
            print("✅ React agent initialized successfully")
            assert test_instance.mobile_agent is not None
        except Exception as e:
            print(f"❌ React agent initialization failed: {e}")
            raise
        
        # クリーンアップ
        try:
            await test_instance._cleanup()
            print("✅ Cleanup completed successfully")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
    
    @pytest.mark.asyncio
    async def test_setup_mobile_agent_complete_flow(self):
        """完全なモバイルエージェント設定フローのテスト"""
        test_instance = AndroidBaseAgentTest()
        
        try:
            await test_instance.setup_mobile_agent()
            print("✅ Complete mobile agent setup successful")
            
            # 初期化後の状態確認
            assert test_instance.tools is not None
            assert test_instance.device_id is not None
            assert test_instance.mobile_agent is not None
            
            print(f"Device ID: {test_instance.device_id}")
            print(f"Tools available: {len(test_instance.tools) if test_instance.tools else 0}")
            print(f"Agent type: {type(test_instance.mobile_agent).__name__}")
            
        except Exception as e:
            print(f"❌ Complete setup failed: {e}")
            raise
        finally:
            # クリーンアップ
            try:
                await test_instance._cleanup()
                print("✅ Final cleanup completed")
            except Exception as e:
                print(f"⚠️ Final cleanup warning: {e}")