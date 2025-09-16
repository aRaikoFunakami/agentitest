# Mobile-MCP 自動テスト効率化設計書

## 1. 現状の問題分析

### パフォーマンス問題
- **実行時間**: 3分43秒（223秒）で1つのシンプルなテスト
- **LLM呼び出し**: 25回（過剰）
- **デバイス検索重複**: 8回（無駄）
- **スクリーンショット取得**: 6回（効率性低い）

### 根本原因
1. **状態管理の欠如**: エージェントがデバイス情報を記憶せず毎回検索
2. **プロンプト設計の問題**: ツール使用方針が不明確
3. **冗長な情報取得**: 必要以上の詳細情報を毎回取得

## 2. 効率化設計

### A. デバイス管理戦略

#### セッション初期化パターン
```
DEVICE_DISCOVERY_PHASE:
1. ONCE: mobile_list_available_devices → デバイス情報をキャッシュ
2. SESSION: デバイスIDを全操作で再利用
3. NEVER: 同一セッション中の再検索禁止
```

#### プロンプト改善
```
DEVICE_MANAGEMENT_RULES:
- デバイスID: {device_id} を全操作で使用
- mobile_list_available_devices は既に実行済み（再実行禁止）
- 画面操作は直接 mobile_* ツールを使用
```

### B. 情報取得最適化

#### スクリーンショット戦略
```
SCREENSHOT_STRATEGY:
- TRIGGER: 明示的な検証要求時のみ
- AVOID: 各ステップでの自動取得
- FORMAT: 必要最小限の解像度
```

#### UI要素取得戦略
```
ELEMENT_DISCOVERY_STRATEGY:
- TARGET_BASED: 特定要素検索時のみ実行
- CACHE_ENABLED: 同一画面では結果再利用
- FILTER_RELEVANT: 関連要素のみ抽出
```

### C. LLMプロンプト最適化

#### タスク分解戦略
```yaml
TASK_DECOMPOSITION:
  単一操作:
    - 1つのmobile_*ツール呼び出し
    - 1つのLLM推論
    - 結果の簡潔な報告
  
  複合操作:
    - 事前計画フェーズ
    - 順次実行フェーズ
    - 検証フェーズ
```

#### コンテキスト管理
```
CONTEXT_OPTIMIZATION:
- ESSENTIAL_ONLY: 必須情報のみ保持
- STEP_MEMORY: 前回操作結果の記憶
- GOAL_FOCUSED: 最終目的への最短経路
```

## 3. 実装設計

### A. 改善されたプロンプトテンプレート

```python
def _get_optimized_mobile_agent_prompt(self, device_id: str) -> str:
    return f"""
ANDROID AUTOMATION AGENT - OPTIMIZED MODE

DEVICE CONTEXT:
- Target Device: {device_id}
- Device discovery: COMPLETED (DO NOT repeat mobile_list_available_devices)

EFFICIENCY RULES:
1. DIRECT EXECUTION: Use mobile_* tools directly with device_id
2. MINIMAL QUERIES: Only essential information gathering
3. SINGLE-PURPOSE: One clear action per LLM call
4. NO REDUNDANCY: Avoid repeated tool calls for same data

AVAILABLE TOOLS (Prioritized):
- mobile_launch_app(device, packageName) - App launching
- mobile_click_on_screen_at_coordinates(device, x, y) - Direct clicking
- mobile_type_keys(device, text, submit) - Text input
- mobile_take_screenshot(device) - ONLY when verification needed
- mobile_list_elements_on_screen(device) - ONLY when element search needed

EXECUTION PATTERN:
1. Plan minimal steps
2. Execute one action
3. Report success/failure briefly
4. Proceed to next action

RESPONSE FORMAT:
- ACTION: [tool used]
- RESULT: [brief outcome]
- NEXT: [if continuation needed]
"""

def _get_task_specific_prompt(self, task: str, device_id: str) -> str:
    return f"""
TASK: {task}
DEVICE: {device_id}

EXECUTION STRATEGY:
- Break task into minimal atomic actions
- Execute each action directly
- Report completion status concisely
- Avoid unnecessary verification steps

Begin execution immediately.
"""
```

### B. 効率化されたエージェント実行

```python
async def execute_optimized_task(self, task: str, device_id: str) -> str:
    """効率化されたタスク実行"""
    
    # 1. 最小限のコンテキスト準備
    optimized_prompt = self._get_task_specific_prompt(task, device_id)
    
    # 2. 制限されたエージェント設定
    efficient_agent = create_react_agent(
        self.llm,
        self.mobile_tools,
        prompt=optimized_prompt,
        # パフォーマンス最適化
        recursion_limit=10,  # 削減
        max_iterations=5,    # 制限
    )
    
    # 3. 実行時間制限
    start_time = time.time()
    timeout = 60  # 1分以内
    
    try:
        result = await asyncio.wait_for(
            efficient_agent.ainvoke({
                "messages": [HumanMessage(content=optimized_prompt)]
            }),
            timeout=timeout
        )
        
        execution_time = time.time() - start_time
        if execution_time > 30:  # 30秒超過で警告
            self.logger.warning(f"Task took {execution_time:.1f}s (target: <30s)")
            
        return result["messages"][-1].content
        
    except asyncio.TimeoutError:
        raise TimeoutError(f"Task execution exceeded {timeout}s timeout")
```

### C. ツール使用ガイドライン

```python
TOOL_USAGE_GUIDELINES = {
    "mobile_list_available_devices": {
        "frequency": "ONCE_PER_SESSION",
        "cache_duration": "ENTIRE_TEST_SESSION",
        "alternative": "Use cached device_id"
    },
    
    "mobile_take_screenshot": {
        "frequency": "ON_DEMAND_ONLY", 
        "triggers": ["verification_required", "error_debugging"],
        "avoid": ["every_step", "information_gathering"]
    },
    
    "mobile_list_elements_on_screen": {
        "frequency": "TARGET_SEARCH_ONLY",
        "cache_strategy": "SAME_SCREEN_REUSE",
        "optimization": "RELEVANT_ELEMENTS_FILTER"
    },
    
    "mobile_click_on_screen_at_coordinates": {
        "priority": "PREFERRED_METHOD",
        "efficiency": "DIRECT_EXECUTION",
        "fallback": "element_search_if_needed"
    }
}
```

## 4. 期待される改善効果

### パフォーマンス目標
```
BEFORE (現状):
- 実行時間: 223秒
- LLM呼び出し: 25回
- デバイス検索: 8回

AFTER (目標):
- 実行時間: <60秒 (73%削減)
- LLM呼び出し: <8回 (68%削減)  
- デバイス検索: 1回 (87%削減)
```

### 品質向上
- **信頼性向上**: タイムアウトによる失敗減少
- **再現性向上**: 一貫した実行パターン
- **保守性向上**: 明確な実行ログ

## 5. 実装優先順位

### Phase 1: 即効性改善
1. デバイス情報キャッシュ実装
2. プロンプト最適化
3. 不要なスクリーンショット削除

### Phase 2: 構造的改善
1. タスク分解アルゴリズム
2. コンテキスト管理改善
3. エラーハンドリング強化

### Phase 3: 高度な最適化
1. 機械学習による操作予測
2. 並行処理実装
3. キャッシュ戦略高度化

## 6. 検証方法

### 性能測定
```python
@dataclass
class PerformanceMetrics:
    execution_time: float
    llm_calls: int
    tool_calls: Dict[str, int]
    success_rate: float
    
def measure_performance(test_function):
    """性能測定デコレータ"""
    start_time = time.time()
    # テスト実行
    metrics = PerformanceMetrics(...)
    assert metrics.execution_time < 60  # 1分以内
    assert metrics.llm_calls < 8       # 8回以内
```

この設計により、現在の223秒から60秒以下への大幅な性能改善が期待できます。
