#!/usr/bin/env python3
"""
Mobile-MCP スクリーンショット取得プログラム
mobile_take_screenshot 専用版

このプログラムは mobile_take_screenshot のみを使用してスクリーンショットを取得します。
成功パターン: {'device': 'emulator-5554'} を使用
"""

import asyncio
import base64
import os
from datetime import datetime
from langchain_mcp_adapters.client import MultiServerMCPClient


async def take_screenshot_with_device(device_id: str = "emulator-5554", save_path: str = None) -> str:
    """
    mobile_take_screenshot を使用してスクリーンショットを取得・保存する
    
    Args:
        device_id: デバイスID (デフォルト: emulator-5554)
        save_path: 保存先ファイルパス (None の場合は自動生成)
    
    Returns:
        str: 保存されたファイルのパス（失敗時は None）
    """
    mcp_client = None
    
    try:
        # 1. MCP クライアントの作成と接続
        print("🔗 MCPサーバーに接続中...")
        
        mcp_client = MultiServerMCPClient({
            "mobile": {
                "transport": "sse",
                "url": "http://localhost:8080/mcp"
            }
        })
        
        # ツールを取得
        mobile_tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=10.0)
        print(f"✅ 接続成功。利用可能なツール数: {len(mobile_tools)}")
        
        # mobile_take_screenshotツールを探す
        screenshot_tool = None
        use_device_tool = None
        
        for tool in mobile_tools:
            tool_name = getattr(tool, 'name', 'unknown')
            if tool_name == 'mobile_take_screenshot':
                screenshot_tool = tool
                print("✅ mobile_take_screenshot ツールを発見")
            elif tool_name == 'mobile_use_device':
                use_device_tool = tool
        
        # mobile_take_screenshotツールが見つからない場合
        if not screenshot_tool:
            print("❌ mobile_take_screenshot ツールが見つかりません")
            print("利用可能なツール:")
            for tool in mobile_tools:
                tool_name = getattr(tool, 'name', 'unknown')
                print(f"  - {tool_name}")
            return None
        
        # デバイス選択（mobile_use_deviceツールがある場合）
        if use_device_tool:
            print(f"デバイス '{device_id}' を選択中...")
            device_result = await use_device_tool.ainvoke({
                "device": device_id,
                "deviceType": "android"
            })
            print(f"device_result: {device_result}")
        
        # 3. スクリーンショットを取得（成功パターンを使用）
        print("📱 mobile_take_screenshot を使用してスクリーンショット取得中...")
        print(f"デバイス: {device_id}")
        
        # 成功パターン: device パラメータを指定
        params = {"device": device_id}
        print(f"パラメータ: {params}")
        
        screenshot_result = await screenshot_tool.ainvoke(params)
        
        # 4. レスポンス解析とデバッグ表示
        print("\n🔍 デバッグ情報:")
        print(f"screenshot_result type: {type(screenshot_result)}")
        print(f"screenshot_result: '{screenshot_result}'")
        print(f"screenshot_result length: {len(str(screenshot_result))}")
        
        # 結果が文字列で、十分な長さがある場合（Base64画像データと判定）
        if isinstance(screenshot_result, str) and len(screenshot_result) > 100:
            try:
                # Data URLの形式をチェック（data:image/png;base64, または data:image/jpeg;base64,）
                base64_data = screenshot_result
                file_extension = "png"
                mime_type = "image/png"
                
                if screenshot_result.startswith("data:"):
                    print("📸 Data URL形式を検出")
                    # Data URLのプレフィックスを解析
                    if "data:image/png;base64," in screenshot_result:
                        base64_data = screenshot_result.split("data:image/png;base64,")[1]
                        file_extension = "png"
                        mime_type = "image/png"
                        print("🖼️  PNG形式として処理")
                    elif "data:image/jpeg;base64," in screenshot_result:
                        base64_data = screenshot_result.split("data:image/jpeg;base64,")[1]
                        file_extension = "jpg"
                        mime_type = "image/jpeg"
                        print("�️  JPEG形式として処理")
                    else:
                        # 汎用的な処理
                        data_url_parts = screenshot_result.split(",")
                        if len(data_url_parts) >= 2:
                            base64_data = data_url_parts[1]
                            print("🖼️  汎用Data URLとして処理")
                else:
                    print("📄 直接Base64文字列として処理")
                
                # 保存先パスを決定（拡張子を適切に設定）
                if not save_path:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    save_path = f"screenshot_{device_id}_{timestamp}.{file_extension}"
                
                print(f"💾 保存先: {save_path}")
                print(f"📊 Base64データ長: {len(base64_data)} 文字")
                
                # Base64デコードしてファイルに保存
                screenshot_bytes = base64.b64decode(base64_data)
                print(f"✅ Base64デコード成功: {len(screenshot_bytes)} bytes")
                
                # ファイルヘッダーを確認
                header_bytes = screenshot_bytes[:16]
                print(f"🔍 ファイルヘッダー (Hex): {header_bytes.hex()}")
                
                # PNG/JPEGヘッダーの検証
                if header_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                    print("✅ 有効なPNGヘッダーを検出")
                    actual_extension = "png"
                elif header_bytes.startswith(b'\xff\xd8\xff'):
                    print("✅ 有効なJPEGヘッダーを検出")
                    actual_extension = "jpg"
                else:
                    print("⚠️  不明な画像ヘッダー - そのまま保存します")
                    actual_extension = file_extension
                
                # 実際のファイル形式と拡張子が異なる場合は修正
                if 'actual_extension' in locals() and actual_extension != file_extension:
                    base_path = save_path.rsplit('.', 1)[0]
                    save_path = f"{base_path}.{actual_extension}"
                    print(f"🔄 拡張子を修正: {save_path}")
                
                with open(save_path, 'wb') as f:
                    f.write(screenshot_bytes)
                
                file_size = len(screenshot_bytes)
                print("\n✅ スクリーンショットを保存しました:")
                print(f"   ファイル: {save_path}")
                print(f"   サイズ: {file_size:,} bytes")
                print(f"   形式: {mime_type}")
                
                return save_path
                
            except Exception as decode_error:
                print(f"❌ Base64デコードエラー: {str(decode_error)}")
                return None
        else:
            print("❌ 有効な画像データが取得できませんでした")
            return None
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")
        print(f"エラータイプ: {type(e).__name__}")
        
        # 詳細なエラー情報を表示
        if hasattr(e, '__cause__') and e.__cause__:
            print(f"原因: {type(e.__cause__).__name__}: {str(e.__cause__)}")
        elif hasattr(e, '__context__') and e.__context__:
            print(f"コンテキスト: {type(e.__context__).__name__}: {str(e.__context__)}")
        
        return None
        
    finally:
        # クリーンアップ処理
        try:
            if mcp_client and hasattr(mcp_client, 'cleanup'):
                await mcp_client.cleanup()
        except Exception:
            pass


async def main():
    """メイン関数"""
    print("📱 Mobile-MCP スクリーンショット取得プログラム")
    print("mobile_take_screenshot 専用版")
    print()
    print("このプログラムは mobile_take_screenshot のみを使用します。")
    print("成功パターン: {'device': 'emulator-5554'} を使用")
    print()
    
    try:
        # デバイスIDを入力
        device_id = input("デバイスID (デフォルト: emulator-5554): ").strip()
        if not device_id:
            device_id = "emulator-5554"
        
        # 保存ファイル名を入力（オプション）
        save_path = input("保存ファイル名 (空白で自動生成): ").strip()
        if not save_path:
            save_path = None
        
        print()
        
    except KeyboardInterrupt:
        print("\nプログラムを終了します。")
        return
    
    # スクリーンショット取得・保存実行
    result_path = await take_screenshot_with_device(device_id, save_path)
    
    if result_path:
        print(f"\n🎉 完了! ファイルが '{result_path}' に保存されました。")
        
        # ファイル情報を表示
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            print("\n📊 ファイル情報:")
            print(f"   パス: {os.path.abspath(result_path)}")
            print(f"   サイズ: {file_size:,} bytes")
            
            # ファイルサイズが適切かチェック
            if file_size > 1000:  # 1KB以上なら正常
                print("   ✅ ファイルサイズは正常です")
            else:
                print("   ⚠️  ファイルサイズが小さすぎる可能性があります")
    else:
        print("\n💥 スクリーンショットの取得に失敗しました。")
        print("\n🔧 トラブルシューティング:")
        print("   1. MCPサーバーが http://localhost:8080 で動作していることを確認")
        print("   2. デバイス（エミュレータ）が起動していることを確認")
        print("   3. デバイスIDが正しいことを確認")
        print("\n詳細なデバッグが必要な場合は mobile_take_screenshot_debug.py を実行してください")


if __name__ == "__main__":
    print("=" * 80)
    print("📱 Mobile-MCP スクリーンショット取得ツール (mobile_take_screenshot 専用)")
    print("=" * 80)
    print("このプログラムは mobile_take_screenshot のみを使用します。")
    print("MCPサーバー: http://localhost:8080")
    print()
    
    # 実行確認
    try:
        answer = input("続行しますか？ (y/N): ").strip().lower()
        if answer not in ['y', 'yes']:
            print("プログラムを終了します。")
            exit(0)
    except KeyboardInterrupt:
        print("\nプログラムを終了します。")
        exit(0)
    
    # 非同期実行
    asyncio.run(main())
