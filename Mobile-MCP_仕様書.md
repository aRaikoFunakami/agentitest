# Mobile-MCP サーバー仕様書

## 概要

Mobile-MCP は、iOS および Android デバイス上でモバイルアプリケーションの自動化とテストを可能にする Model Context Protocol (MCP) サーバーです。LLM エージェントがモバイルアプリケーションを操作できるよう、アクセシビリティツリーやスクリーンショットベースのインタラクション機能を提供します。

## アーキテクチャ

### MCP サーバー構造

```
mobile-mcp/
├── src/
│   ├── mobile_mcp/
│   │   ├── __init__.py
│   │   ├── server.py           # MCP サーバーエントリーポイント
│   │   ├── robot/
│   │   │   ├── __init__.py
│   │   │   ├── robot.py        # Robot 抽象基底クラス
│   │   │   ├── android.py      # AndroidRobot 実装
│   │   │   └── ios.py          # IosRobot 実装
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── device.py       # デバイス関連ツール
│   │       ├── app.py          # アプリ関連ツール
│   │       └── interaction.py  # インタラクション関連ツール
```

### Robot インターフェース

```python
class Robot(ABC):
    """モバイルデバイス操作の抽象基底クラス"""
    
    @abstractmethod
    def get_accessibility_tree(self) -> str:
        """アクセシビリティツリーの取得"""
        pass
    
    @abstractmethod
    def take_screenshot(self) -> str:
        """スクリーンショットの取得（Base64エンコード）"""
        pass
    
    @abstractmethod
    def tap(self, x: int, y: int) -> bool:
        """座標指定タップ"""
        pass
    
    @abstractmethod
    def type_keys(self, text: str) -> bool:
        """テキスト入力"""
        pass
    
    @abstractmethod
    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """スワイプ操作"""
        pass
```

## MCP ツール一覧

### 1. デバイス管理ツール

#### mobile_use_device
```python
{
    "name": "mobile_use_device",
    "description": "Connect to mobile device",
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string", "description": "Device ID (udid for iOS, adb device id for Android)"},
            "platform": {"type": "string", "enum": ["ios", "android"], "description": "Device platform"}
        },
        "required": ["device_id", "platform"]
    }
}
```

#### mobile_list_devices
```python
{
    "name": "mobile_list_devices", 
    "description": "List available mobile devices",
    "inputSchema": {
        "type": "object",
        "properties": {
            "platform": {"type": "string", "enum": ["ios", "android", "all"], "description": "Filter by platform"}
        }
    }
}
```

#### mobile_get_device_info
```python
{
    "name": "mobile_get_device_info",
    "description": "Get device information",
    "inputSchema": {"type": "object", "properties": {}}
}
```

### 2. アプリケーション管理ツール

#### mobile_list_apps
```python
{
    "name": "mobile_list_apps",
    "description": "List installed applications",
    "inputSchema": {
        "type": "object", 
        "properties": {
            "app_type": {"type": "string", "enum": ["user", "system", "all"], "description": "Application type filter"}
        }
    }
}
```

#### mobile_launch_app
```python
{
    "name": "mobile_launch_app",
    "description": "Launch application",
    "inputSchema": {
        "type": "object",
        "properties": {
            "bundle_id": {"type": "string", "description": "Application bundle ID"}
        },
        "required": ["bundle_id"]
    }
}
```

#### mobile_get_current_app
```python
{
    "name": "mobile_get_current_app",
    "description": "Get current application information",
    "inputSchema": {"type": "object", "properties": {}}
}
```

#### mobile_close_app
```python
{
    "name": "mobile_close_app", 
    "description": "Close application",
    "inputSchema": {
        "type": "object",
        "properties": {
            "bundle_id": {"type": "string", "description": "Application bundle ID"}
        },
        "required": ["bundle_id"]
    }
}
```

### 3. インタラクション ツール

#### mobile_take_screenshot
```python
{
    "name": "mobile_take_screenshot",
    "description": "Take screenshot of current screen",
    "inputSchema": {"type": "object", "properties": {}}
}
```

#### mobile_get_accessibility_tree
```python
{
    "name": "mobile_get_accessibility_tree",
    "description": "Get accessibility tree of current screen",
    "inputSchema": {"type": "object", "properties": {}}
}
```

#### mobile_tap
```python
{
    "name": "mobile_tap",
    "description": "Tap at coordinates",
    "inputSchema": {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "X coordinate"},
            "y": {"type": "number", "description": "Y coordinate"}
        },
        "required": ["x", "y"]
    }
}
```

#### mobile_tap_element
```python
{
    "name": "mobile_tap_element",
    "description": "Tap element by accessibility identifier",
    "inputSchema": {
        "type": "object",
        "properties": {
            "element_id": {"type": "string", "description": "Accessibility identifier"},
            "text": {"type": "string", "description": "Element text content (alternative identifier)"}
        }
    }
}
```

#### mobile_type_keys
```python
{
    "name": "mobile_type_keys",
    "description": "Type text input",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to type"}
        },
        "required": ["text"]
    }
}
```

#### mobile_swipe
```python
{
    "name": "mobile_swipe",
    "description": "Swipe gesture",
    "inputSchema": {
        "type": "object",
        "properties": {
            "start_x": {"type": "number", "description": "Start X coordinate"},
            "start_y": {"type": "number", "description": "Start Y coordinate"},
            "end_x": {"type": "number", "description": "End X coordinate"},
            "end_y": {"type": "number", "description": "End Y coordinate"},
            "duration": {"type": "number", "description": "Swipe duration in seconds", "default": 0.5}
        },
        "required": ["start_x", "start_y", "end_x", "end_y"]
    }
}
```

#### mobile_scroll
```python
{
    "name": "mobile_scroll",
    "description": "Scroll in specified direction",
    "inputSchema": {
        "type": "object",
        "properties": {
            "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Scroll direction"},
            "distance": {"type": "number", "description": "Scroll distance (0.1-1.0)", "default": 0.5}
        },
        "required": ["direction"]
    }
}
```

#### mobile_long_press
```python
{
    "name": "mobile_long_press",
    "description": "Long press at coordinates",
    "inputSchema": {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "X coordinate"},
            "y": {"type": "number", "description": "Y coordinate"},
            "duration": {"type": "number", "description": "Press duration in seconds", "default": 1.0}
        },
        "required": ["x", "y"]
    }
}
```

### 4. システム操作ツール

#### mobile_press_key
```python
{
    "name": "mobile_press_key", 
    "description": "Press system key",
    "inputSchema": {
        "type": "object",
        "properties": {
            "key": {"type": "string", "enum": ["home", "back", "menu", "volume_up", "volume_down", "power"], "description": "System key"}
        },
        "required": ["key"]
    }
}
```

#### mobile_set_orientation
```python
{
    "name": "mobile_set_orientation",
    "description": "Set device orientation",
    "inputSchema": {
        "type": "object",
        "properties": {
            "orientation": {"type": "string", "enum": ["portrait", "landscape"], "description": "Device orientation"}
        },
        "required": ["orientation"]
    }
}
```

## Android 実装詳細

### AndroidRobot クラス

```python
class AndroidRobot(Robot):
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.driver = None  # Appium WebDriver
    
    def connect(self) -> bool:
        """デバイスへの接続"""
        desired_caps = {
            "platformName": "Android",
            "deviceName": self.device_id,
            "automationName": "UiAutomator2",
            "noReset": True
        }
        try:
            self.driver = webdriver.Remote("http://localhost:4723", desired_caps)
            return True
        except Exception:
            return False
    
    def get_accessibility_tree(self) -> str:
        """UI階層の取得"""
        return self.driver.page_source
    
    def take_screenshot(self) -> str:
        """スクリーンショットのBase64エンコード"""
        return self.driver.get_screenshot_as_base64()
    
    def tap(self, x: int, y: int) -> bool:
        """タップ操作"""
        try:
            self.driver.tap([(x, y)])
            return True
        except Exception:
            return False
```

### 依存関係

- `appium-python-client`: Appium WebDriver
- `selenium`: WebDriver 基盤
- `fastmcp`: MCP サーバーフレームワーク
- `pillow`: 画像処理
- `base64`: エンコーディング

## iOS 実装詳細

### IosRobot クラス

```python
class IosRobot(Robot):
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.driver = None  # Appium WebDriver (XCUITest)
    
    def connect(self) -> bool:
        """デバイスへの接続"""
        desired_caps = {
            "platformName": "iOS",
            "deviceName": self.device_id,
            "automationName": "XCUITest",
            "noReset": True
        }
        try:
            self.driver = webdriver.Remote("http://localhost:4723", desired_caps)
            return True
        except Exception:
            return False
```

### 依存関係（iOS 追加）

- `WebDriverAgent`: iOS デバイス制御
- `libimobiledevice`: iOS デバイス通信
- `ios-deploy`: アプリデプロイメント

## MCP サーバー設定例

### stdio トランスポート設定

```json
{
  "mcpServers": {
    "mobile": {
      "command": "python",
      "args": ["-m", "mobile_mcp.server"],
      "env": {
        "APPIUM_SERVER": "http://localhost:4723",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### streamable-http トランスポート設定

```python
# mobile_mcp/http_server.py
from fastmcp import FastMCP
from mobile_mcp.tools import get_all_tools

app = FastMCP("Mobile MCP")

# ツールの登録
for tool in get_all_tools():
    app.register_tool(tool)

if __name__ == "__main__":
    app.run(transport="streamable_http", port=8080)
```

## 使用例

### LangChain MCP Adapters との統合

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

client = MultiServerMCPClient({
    "mobile": {
        "command": "python",
        "args": ["-m", "mobile_mcp.server"],
        "transport": "stdio"
    }
})

tools = await client.get_tools()
agent = create_react_agent("openai:gpt-4", tools)

# モバイルアプリテストの実行
response = await agent.ainvoke({
    "messages": ["AndroidデバイスでChromeを起動してyahoo.co.jpを開いてください"]
})
```

## エラーハンドリング

### 共通エラータイプ

1. **DeviceNotConnectedError**: デバイス未接続
2. **AppNotFoundError**: アプリケーション見つからず
3. **ElementNotFoundError**: UI要素見つからず
4. **OperationTimeoutError**: 操作タイムアウト
5. **PlatformNotSupportedError**: プラットフォーム未対応

### エラーレスポンス形式

```json
{
  "isError": true,
  "content": [
    {
      "type": "text",
      "text": "Device not connected: 192.168.1.100:5555"
    }
  ]
}
```

## パフォーマンス考慮事項

### 最適化ポイント

1. **スクリーンショットキャッシュ**: 連続操作時の重複取得回避
2. **アクセシビリティツリー差分**: 変更部分のみの取得
3. **コネクションプール**: 複数デバイス接続時の効率化
4. **非同期操作**: 並列テスト実行対応

### リソース制限

- 同時接続デバイス数: 10台まで推奨
- スクリーンショット最大サイズ: 2MB
- アクセシビリティツリー最大ノード数: 1000個

## セキュリティ

### アクセス制御

- デバイス ID による接続制限
- アプリケーション Bundle ID ホワイトリスト
- システム領域アクセス制限

### データ保護

- スクリーンショット自動削除（30秒後）
- 入力テキストログ無効化オプション
- セッション暗号化（TLS 1.3）
