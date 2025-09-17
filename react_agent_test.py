# Comments are in English as requested.
import asyncio
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
import requests
from langchain.tools import tool

ENABLE_TOKEN_STREAM = False  # Set True to see token-by-token output from chat_model

# Rationale-lite settings (safe summaries of decisions)
ENABLE_DECISION_SUMMARY = True
TOOL_REASON_MAP = {
    "get_weather": "リアルタイムの天気データを取得するため",
}

model = init_chat_model("openai:gpt-4o-mini", temperature=0)

# ---- Tools ----
@tool
def get_weather(city: str) -> str:
    """Get real-time weather for a city using wttr.in public API and summarize briefly in Japanese."""
    # This is a simple HTTP call to a public endpoint. No API key required.
    url = f"https://wttr.in/{city}?format=j1"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        cur = data.get("current_condition", [{}])[0]
        # Extract a few useful fields
        temp_c = cur.get("temp_C")
        feels_c = cur.get("FeelsLikeC")
        humidity = cur.get("humidity")
        wind_kph = cur.get("windspeedKmph")
        desc = "".join([d.get("value", "") for d in cur.get("weatherDesc", [])])
        # Compose a short JP summary
        parts = []
        if temp_c is not None:
            parts.append(f"気温 {temp_c}℃")
        if feels_c is not None:
            parts.append(f"体感 {feels_c}℃")
        if humidity is not None:
            parts.append(f"湿度 {humidity}%")
        if wind_kph is not None:
            parts.append(f"風速 {wind_kph}km/h")
        summary = " / ".join(parts)
        if desc:
            summary = f"{desc} / {summary}" if summary else desc
        return f"{city} の現在の天気: {summary}"
    except Exception as e:
        return f"天気取得に失敗しました: {e}"

tools = [get_weather]
agent = create_react_agent(model, tools)

# ---- Reusable event printer (for astream_events) ----
class EventPrinter:
    """Pretty-printer for LangGraph astream_events.
    This class prints only observable signals (no chain-of-thought):
    - node start/end
    - LLM streaming tokens (optional)
    - final LLM outputs when provider buffers
    - tool start/end with args and outputs
    Configuration can be passed at construction for reuse.
    """

    def __init__(self,
                 enable_token_stream: bool = ENABLE_TOKEN_STREAM,
                 tool_reason_map: dict | None = None,
                 verbose: bool = False):
        self.enable_token_stream = enable_token_stream
        self.tool_reason_map = tool_reason_map or TOOL_REASON_MAP
        self.verbose = verbose

    # --- helpers ---
    def _print_llm_token(self, ev):
        data = ev.get("data", {})
        tok = data.get("token")
        if isinstance(tok, str):
            print(tok, end="", flush=True)
            return
        chunk = data.get("chunk")
        if chunk is not None:
            text = None
            if isinstance(chunk, dict):
                if chunk.get("tool_calls") or chunk.get("function_call"):
                    return
                text = chunk.get("content") or chunk.get("delta") or chunk.get("text")
            else:
                text = getattr(chunk, "content", None) or getattr(chunk, "delta", None)
                ak = getattr(chunk, "additional_kwargs", None)
                if ak and (ak.get("tool_calls") or ak.get("function_call")):
                    return
            if isinstance(text, list):
                for part in text:
                    if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                        print(part["text"], end="", flush=True)
                return
            if isinstance(text, str) and text:
                print(text, end="", flush=True)
                return
            return
        if "bytes" in data and isinstance(data["bytes"], (bytes, bytearray)):
            try:
                print(data["bytes"].decode("utf-8", errors="ignore"), end="", flush=True)
            except Exception:
                pass
            return
        return

    def _print_llm_end(self, ev):
        data = ev.get("data", {})
        out = data.get("output")
        text = None
        if isinstance(out, dict):
            text = out.get("content") or out.get("text")
            if isinstance(text, list):
                parts = []
                for part in text:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
                text = "".join(parts) if parts else None
        else:
            text = getattr(out, "content", None)
            if text is None and out is not None:
                text = str(out)
        if isinstance(text, str) and text:
            print(f"\n[LLM:FINAL] {text}")

    # --- public handlers ---
    def on_node_start(self, ev):
        node = ev.get("data", {}).get("node_name")
        print(f"[NODE:START] {node}")

    def on_node_end(self, ev):
        node = ev.get("data", {}).get("node_name")
        print(f"[NODE:END]   {node}")

    def on_tool_start(self, ev):
        d = ev.get("data", {})
        name = ev.get("name") or "<tool>"
        print(f"[TOOL:START] {name} args={d.get('input')}")

    def on_tool_end(self, ev):
        d = ev.get("data", {})
        name = ev.get("name") or "<tool>"
        print(f"[TOOL:END] {name} output={d.get('output').content}")

    
    def _print_on_chat_model_end(self, ev):
        # ev['data']['output'] が AIMessage インスタンス
        ai_msg = ev['data']['output'].content
        ai_msg = " ".join(ai_msg.split())  # Normalize whitespace
        print(f"[LLM MODEL]: {ai_msg}")


    def _print_on_chain_start(self, ev):
        if self.verbose:
            print(f"[CHAIN START]: {ev.get('name')}")

    def _print_on_chain_end(self, ev):
        data = ev.get('data', {})
        output = data.get('output')
        if ev.get('name') == 'should_continue' and output:
            print("[CHAIN END]: should_continue,", output if not isinstance(output, list) else output[0])
        elif self.verbose:
            print(f"[CHAIN END]: {ev.get('name')},")


    def dispatch(self, ev):
        et = ev.get("event", "")
        
        if et.endswith("node_start"):
            self.on_node_start(ev)
        elif et.endswith("node_end"):
            self.on_node_end(ev)
        elif et.endswith("tool_start"):
            self.on_tool_start(ev)
        elif et.endswith("tool_end"):
            self.on_tool_end(ev)
        elif et.endswith("on_chat_model_end"):
            self._print_on_chat_model_end(ev)
        elif et.endswith("on_chain_start"):
            self._print_on_chain_start(ev)
        elif et.endswith("on_chain_end"):
            self._print_on_chain_end(ev)
        elif self.enable_token_stream and (("chat_model" in et and et.endswith("stream")) or ("llm" in et and et.endswith("stream"))):
            d = ev.get("data", {})
            if any(k in d for k in ("token", "chunk", "bytes")):
                self._print_llm_token(ev)
        elif ("chat_model" in et and et.endswith("end")) or ("llm" in et and et.endswith("end")):
            self._print_llm_end(ev)

async def main():
    inputs = {"messages": [
        ("system", (
            "あなたは利用可能なツールを適切に呼び出して最新情報を取得できます。"
            "リアルタイム情報は必ずツールを使って取得してください。"
        )),
        ("user", "東京の天気を調べて、要約して、まずユーザーの司令に対して方針を立て、その方針を出力しなさい")
    ]}

    printer = EventPrinter()
    final_output = None  # ← 追加
    async for ev in agent.astream_events(inputs, version="v2"):
        printer.dispatch(ev)
        # "node_end" で最終出力を取得
        if ev.get("event", "").endswith("on_chat_model_end"):
            final_output = ev.get("data", {}).get("output")
    print("\n--- done ---")
    print("最終出力:", final_output.content)  # ← 追加

    print("\n--- done ---")

asyncio.run(main())