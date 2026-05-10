"""
Northern Trail Outfitters (NTO) Shopping Agent
Uses Claude API with custom tools to search NTO's catalog via Salesforce Commerce Cloud (SCAPI)
"""

import json
import os
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from duckduckgo_search import DDGS
from system_prompt import get_system_prompt
from customer_prompts import get_system_prompt_for_customer


def _ms(start: float) -> str:
    return f"{(time.monotonic() - start) * 1000:.0f}ms"


class NTOAgent:
    def __init__(self, api_key: str, base_url: str = None,
                 scapi_token_url: str = None, scapi_client_credentials: str = None,
                 scapi_search_url: str = None, scapi_site_id: str = "NTOManaged",
                 customer_id: str = None):

        if base_url:
            self.client = Anthropic(api_key=api_key, base_url=base_url)
            self.model = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        else:
            self.client = Anthropic(api_key=api_key)
            self.model = "claude-opus-4-7"

        # SCAPI configuration
        self.scapi_token_url = scapi_token_url
        self.scapi_client_credentials = scapi_client_credentials
        self.scapi_search_url = scapi_search_url
        self.scapi_site_id = scapi_site_id

        # Token cache — lock prevents concurrent threads from double-minting
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._token_lock = threading.Lock()

        # Product cache for details lookups
        self.product_cache: Dict[str, Dict] = {}

        self.customer_id = customer_id
        self.system_prompt = get_system_prompt_for_customer(customer_id)
        self.conversation_history = []

    # ── SCAPI token management ──────────────────────────────────────────────

    def _get_access_token(self) -> str:
        """Return a valid bearer token, refreshing if within 60s of expiry."""
        with self._token_lock:
            if self._access_token and time.monotonic() < self._token_expires_at - 60:
                return self._access_token

            t0 = time.monotonic()
            resp = requests.post(
                self.scapi_token_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {self.scapi_client_credentials}",
                },
                data={
                    "grant_type": "client_credentials",
                    "channel_id": self.scapi_site_id,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expires_at = time.monotonic() + data.get("expires_in", 1800)
            print(f"  ⏱  SCAPI token refresh: {_ms(t0)}")
            return self._access_token

    # ── SCAPI product search ────────────────────────────────────────────────

    def _call_scapi_search(self, query_text: str, category: str = None,
                           min_price: float = 0, max_price: float = float("inf"),
                           max_results: int = 10) -> List[Dict]:
        """Call the SCAPI Shopper Search endpoint."""
        t0 = time.monotonic()
        try:
            token = self._get_access_token()

            params: Dict[str, Any] = {
                "q": query_text,
                "limit": max_results,
                "siteId": self.scapi_site_id,
            }
            if category:
                params["refine"] = f"cgid={category}"

            resp = requests.get(
                self.scapi_search_url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            resp.raise_for_status()
            print(f"  ⏱  SCAPI search '{query_text[:40]}': {_ms(t0)}")

            hits = resp.json().get("hits", [])
            products = []
            for hit in hits:
                price = hit.get("price")
                if price is not None:
                    if price < min_price or price > max_price:
                        continue

                product = {
                    "id": hit.get("productId", ""),
                    "name": hit.get("productName", ""),
                    "brand": "",  # SCAPI doesn't surface brand at search level
                    "price": price,
                    "category": self._extract_category(hit),
                    "description": self._clean_html(hit.get("c_description", "")),
                    "image_url": hit.get("c_imageUrl", hit.get("image", {}).get("link", "")),
                    "rating": None,
                    "product_url": hit.get("c_productUrl", ""),
                }
                products.append(product)
                if product["id"]:
                    self.product_cache[product["id"]] = product

            return products

        except Exception as e:
            print(f"⚠️  SCAPI search error ({_ms(t0)}): {e}")
            return []

    @staticmethod
    def _extract_category(hit: Dict) -> str:
        """Pull first category label from refinements hit data if present."""
        for ra in hit.get("variationAttributes", []):
            if ra.get("id") == "cgid":
                vals = ra.get("values", [])
                if vals:
                    return vals[0].get("name", "")
        return ""

    @staticmethod
    def _clean_html(text: str) -> str:
        """Strip basic HTML tags for clean description text."""
        import re
        return re.sub(r"<[^>]+>", " ", text).strip()[:300]

    # ── Agent tools ─────────────────────────────────────────────────────────

    def search_products(self, queries: List[Dict]) -> Dict[str, Any]:
        """Search the NTO catalog — all queries fired in parallel."""
        t0 = time.monotonic()
        n = len(queries)
        print(f"  ⏱  search_products: {n} quer{'y' if n == 1 else 'ies'} (parallel)")
        results = {}

        def _run(i: int, query: Dict):
            matches = self._call_scapi_search(
                query.get("q", ""),
                category=query.get("category") or None,
                min_price=query.get("min_price", 0),
                max_price=query.get("max_price", float("inf")),
                max_results=20,
            )
            return i, query, matches

        with ThreadPoolExecutor(max_workers=min(n, 5)) as executor:
            futures = [executor.submit(_run, i, q) for i, q in enumerate(queries)]
            for future in as_completed(futures):
                i, query, matches = future.result()
                results[f"query_{i}"] = {
                    "query": query,
                    "count": len(matches),
                    "products": matches[:10],
                }

        print(f"  ⏱  search_products total: {_ms(t0)}")
        return results

    def get_product_details(self, product_ids: List[str]) -> Dict[str, Any]:
        """Return cached product details."""
        return {
            pid: self.product_cache.get(pid, {"error": "Product not found"})
            for pid in product_ids
        }

    def _get_tools(self) -> List[Dict]:
        return [
            {
                "name": "create_todo",
                "description": "Create a plan before executing tool calls.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "steps": {"type": "array", "items": {"type": "string"}},
                        "message": {"type": "string"},
                    },
                    "required": ["steps", "message"],
                },
            },
            {
                "name": "search_nto_products",
                "description": "Search the Northern Trail Outfitters catalog for outdoor gear, apparel, and footwear.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "q": {"type": "string", "description": "Keyword search (product type, brand, activity, feature)"},
                                    "category": {"type": "string", "description": "Category ID filter: men, women, kids, gear"},
                                    "min_price": {"type": "number"},
                                    "max_price": {"type": "number"},
                                },
                            },
                        }
                    },
                    "required": ["queries"],
                },
            },
            {
                "name": "get_nto_product_details",
                "description": "Fetch full details for up to 5 NTO product IDs.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_ids": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["product_ids"],
                },
            },
            {
                "name": "web_search",
                "description": "Search the web for gear reviews, trail conditions, or activity tips.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict) -> Any:
        if tool_name == "search_nto_products":
            return self.search_products(tool_input.get("queries", []))
        elif tool_name == "get_nto_product_details":
            return self.get_product_details(tool_input.get("product_ids", []))
        elif tool_name == "create_todo":
            return {"status": "plan_created", "steps": tool_input.get("steps", []), "message": tool_input.get("message", "")}
        elif tool_name == "web_search":
            return self.web_search(tool_input.get("query", ""), min(tool_input.get("max_results", 5), 10))
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def web_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        t0 = time.monotonic()
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            print(f"  ⏱  DuckDuckGo '{query[:40]}': {_ms(t0)} ({len(results)} results)")
            return {
                "query": query,
                "results": [{"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")} for r in results],
            }
        except Exception as e:
            print(f"  ⚠️  Web search error ({_ms(t0)}): {e}")
            return {"query": query, "results": [], "error": str(e)}

    def _analyze_image_and_create_query(self, image: bytes, user_message: str) -> tuple:
        """Use Claude's vision to analyze a gear image and create search queries."""
        try:
            import base64, re as _re

            image_base64 = base64.b64encode(image).decode("utf-8")
            if image[:4] == b"\x89PNG":
                media_type = "image/png"
            elif image[:4] == b"GIF8":
                media_type = "image/gif"
            elif image[:4] == b"RIFF" and image[8:12] == b"WEBP":
                media_type = "image/webp"
            else:
                media_type = "image/jpeg"

            vision_prompt = """Analyze this outdoor gear or apparel image CAREFULLY.

STEP 1 — READ ALL TEXT ON THE PRODUCT FIRST.
Read brand name, product name, product type, key features. Do not guess brand names — only use what is written.

STEP 2 — IDENTIFY EACH PRODUCT.
- Exact brand name (from label — DO NOT GUESS)
- Product type (hiking boot, rain jacket, tent, backpack, etc.)
- Key visible features (waterproof, insulated, etc.)

STEP 3 — BUILD SEARCH QUERIES. Brand first if readable.
Good: "Patagonia rain jacket", "Merrell hiking boot waterproof"
Bad: "outdoor jacket" (no brand)

Respond in this EXACT format:
DESCRIPTION: [what you see]
QUERIES: [comma-separated queries, one per product]"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                        {"type": "text", "text": vision_prompt},
                    ],
                }],
            )

            response_text = next((b.text.strip() for b in response.content if b.type == "text"), "")
            description, queries = "", []
            for line in response_text.split("\n"):
                if line.startswith("DESCRIPTION:"):
                    description = line.replace("DESCRIPTION:", "").strip()
                elif line.startswith("QUERIES:"):
                    queries = [q.strip() for q in line.replace("QUERIES:", "").split(",") if q.strip()]

            if not queries:
                queries = ["outdoor gear"]
            if not description:
                description = "Outdoor product(s) in image"

            print(f"  🔍 Vision: {description} → {queries}")
            return queries, description, media_type, response_text

        except Exception as e:
            print(f"  ⚠️  Vision error: {e}")
            return ["outdoor gear"], "Outdoor product in image", "unknown", str(e)

    # ── Main chat loop ───────────────────────────────────────────────────────

    def chat(self, user_message: str, max_iterations: int = 5, image: bytes = None) -> Dict:
        image_analysis = None
        if image:
            queries, description, media_type, raw = self._analyze_image_and_create_query(image, user_message)
            image_analysis = {"description": description, "queries": queries, "media_type": media_type, "raw_vision_response": raw}
            user_note = user_message if user_message and user_message != "Visual search" else ""
            user_message = f"{user_note} — {', '.join(queries)}" if user_note else ", ".join(queries)

        self.conversation_history.append({"role": "user", "content": user_message})

        iteration, assistant_message, tool_call_log = 0, "", []
        chat_t0 = time.monotonic()

        while iteration < max_iterations:
            iteration += 1
            print(f"\n🔄 ReAct Iteration {iteration}/{max_iterations}")

            claude_t0 = time.monotonic()
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                tools=self._get_tools(),
                messages=self.conversation_history,
            )
            print(f"  ⏱  Claude: {_ms(claude_t0)} (in={response.usage.input_tokens}, out={response.usage.output_tokens})")

            assistant_message, tool_results, has_tool_use = "", [], False

            for block in response.content:
                if block.type == "text":
                    assistant_message = block.text
                elif block.type == "tool_use":
                    has_tool_use = True
                    t0 = time.monotonic()
                    print(f"  🔧 Tool: {block.name}")
                    result = self._execute_tool(block.name, block.input)
                    duration = _ms(t0)
                    tool_call_log.append({"tool": block.name, "input": block.input, "duration": duration})
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})

            self.conversation_history.append({"role": "assistant", "content": response.content})

            if not has_tool_use:
                print("  ✅ Final response")
                break

            self.conversation_history.append({"role": "user", "content": tool_results})

        print(f"\n⏱  TOTAL: {_ms(chat_t0)} across {iteration} iteration(s)")

        cleaned = assistant_message.strip()
        for marker in ("```json", "```"):
            if cleaned.startswith(marker):
                cleaned = cleaned[len(marker):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            if image_analysis:
                parsed["image_analysis"] = image_analysis
            parsed["tool_call_log"] = tool_call_log
            return parsed
        except json.JSONDecodeError:
            fallback = {
                "thought": "Raw response",
                "response": [{"type": "markdown", "content": assistant_message}],
                "follow_up": "How else can I help you find the right gear?",
                "suggestions": [],
                "tool_call_log": tool_call_log,
            }
            if image_analysis:
                fallback["image_analysis"] = image_analysis
            return fallback

    def reset(self):
        self.conversation_history = []


def main():
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        return

    agent = NTOAgent(
        api_key=api_key,
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        scapi_token_url=os.getenv("SCAPI_TOKEN_URL"),
        scapi_client_credentials=os.getenv("SCAPI_CLIENT_CREDENTIALS"),
        scapi_search_url=os.getenv("SCAPI_SEARCH_URL"),
        scapi_site_id=os.getenv("SCAPI_SITE_ID", "NTOManaged"),
    )

    print("🏔️  Northern Trail Outfitters Shopping Agent")
    print("="*60)
    print("💬 Type 'quit' to exit, 'reset' to start new conversation\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Thanks for shopping with Northern Trail Outfitters!")
            break
        if user_input.lower() == "reset":
            agent.reset()
            print("🔄 Conversation reset.\n")
            continue
        if not user_input:
            continue

        try:
            response = agent.chat(user_input)
            print("\n" + "="*60)
            print("NTO Trail Advisor:")
            print("="*60)
            if "thought" in response:
                print(f"\n💭 {response['thought']}\n")
            for block in response.get("response", []):
                if block["type"] == "markdown":
                    print(block["content"])
            if response.get("follow_up"):
                print(f"\n❓ {response['follow_up']}")
            if response.get("suggestions"):
                print("\n💡 " + " | ".join(response["suggestions"]))
            print()
        except Exception as e:
            import traceback
            print(f"❌ {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
