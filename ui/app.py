"""
Northern Trail Outfitters (NTO) Shopping Agent - Web UI
Simple Streamlit interface for the NTO outdoor shopping agent
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add parent directory to path to import agent
sys.path.append(str(Path(__file__).parent.parent / "agent"))

from nto_agent import NTOAgent
from customer_prompts import list_customers
from dotenv import load_dotenv

# Load environment variables — local .env first, then Streamlit secrets
load_dotenv()
try:
    for key, val in st.secrets.items():
        if key not in os.environ:
            os.environ[key] = str(val)
except Exception:
    pass

# Page config
st.set_page_config(
    page_title="NTO Trail Advisor",
    page_icon="🏔️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #000000;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: bold;
    }
    .sub-header {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #F8E8F0;
    }
    .assistant-message {
        background-color: #FFF5F5;
    }
    .suggestion-button {
        margin: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

def _build_agent(customer_id: str) -> NTOAgent:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("❌ ANTHROPIC_API_KEY not found! Please set it in .env file.")
        st.stop()

    scapi_token_url = os.getenv("SCAPI_TOKEN_URL")
    scapi_credentials = os.getenv("SCAPI_CLIENT_CREDENTIALS")
    scapi_search_url = os.getenv("SCAPI_SEARCH_URL")
    scapi_site_id = os.getenv("SCAPI_SITE_ID", "NTOManaged")

    if not all([scapi_token_url, scapi_credentials, scapi_search_url]):
        st.error("❌ SCAPI credentials not found! Check SCAPI_TOKEN_URL, SCAPI_CLIENT_CREDENTIALS, SCAPI_SEARCH_URL in .env")
        st.stop()

    return NTOAgent(
        api_key=api_key,
        base_url=os.getenv("ANTHROPIC_BASE_URL"),
        scapi_token_url=scapi_token_url,
        scapi_client_credentials=scapi_credentials,
        scapi_search_url=scapi_search_url,
        scapi_site_id=scapi_site_id,
        customer_id=customer_id or None,
    )


# Initialize session state
if 'customer_id' not in st.session_state:
    st.session_state.customer_id = os.getenv("SCAPI_SITE_ID", "NTOManaged")

if 'agent' not in st.session_state:
    st.session_state.agent = _build_agent(st.session_state.customer_id)

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'suggestions' not in st.session_state:
    st.session_state.suggestions = []

if 'pending_input' not in st.session_state:
    st.session_state.pending_input = None

if 'message_responses' not in st.session_state:
    st.session_state.message_responses = []  # Store full response structures

if 'staged_image' not in st.session_state:
    st.session_state.staged_image = None

# Header
st.markdown('<div class="main-header">🏔️ NTO Trail Advisor</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Gear up for your next adventure — hiking, camping, climbing & more</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("About")
    st.write("""
    Your **Northern Trail Outfitters** gear advisor, helping you find:

    🥾 **Hiking** - Boots, poles, daypacks, navigation
    🏕️ **Camping** - Tents, sleeping bags, cook systems
    🧗 **Climbing** - Harnesses, shoes, protection
    🏃 **Trail Running** - Shoes, hydration vests, apparel
    🚴 **Cycling** - Bikes, helmets, apparel, accessories
    ⛷️ **Snow Sports** - Skis, snowboards, outerwear
    🌊 **Water Sports** - Kayaking, paddleboarding, wetsuits
    """)

    st.divider()

    # Customer selector
    customers = list_customers()
    customer_options = ["(base — no overlay)"] + customers
    current_idx = (customers.index(st.session_state.customer_id) + 1
                   if st.session_state.customer_id in customers else 0)
    selected = st.selectbox("Customer profile", customer_options, index=current_idx)
    new_customer_id = None if selected == "(base — no overlay)" else selected

    if new_customer_id != st.session_state.customer_id:
        st.session_state.customer_id = new_customer_id
        st.session_state.agent = _build_agent(new_customer_id)
        st.session_state.messages = []
        st.session_state.suggestions = []
        st.session_state.message_responses = []
        st.rerun()

    if st.session_state.customer_id:
        st.caption(f"Overlay active: `{st.session_state.customer_id}`")
    else:
        st.caption("Using base prompt only")

    st.divider()

    cache_size = len(st.session_state.agent.product_cache)
    st.metric("Products Cached", cache_size)

    if st.button("🔄 Reset Conversation"):
        st.session_state.agent.reset()
        st.session_state.messages = []
        st.session_state.suggestions = []
        st.session_state.staged_image = None
        st.rerun()

    st.divider()
    st.caption("Powered by Claude AI | Northern Trail Outfitters")

# Handle pending suggestion click FIRST (before rendering anything else)
user_input_from_suggestion = None
if 'pending_input' in st.session_state and st.session_state.pending_input:
    user_input_from_suggestion = st.session_state.pending_input
    st.session_state.pending_input = None
    # Clear suggestions so they don't show again
    st.session_state.suggestions = []

# Display chat messages using Streamlit's chat interface
assistant_message_count = 0
for idx, message in enumerate(st.session_state.messages):
    if message["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            # Show image if present
            if "image" in message and message["image"]:
                st.image(message["image"], width=200)
            st.markdown(message["content"])
    else:
        with st.chat_message("assistant", avatar="🏔️"):
            # Check if we have the full response structure stored
            if assistant_message_count < len(st.session_state.message_responses):
                response_data = st.session_state.message_responses[assistant_message_count]

                # Show image analysis if present
                if response_data and 'image_analysis' in response_data:
                    analysis = response_data['image_analysis']
                    st.info(f"🔍 **Image Analysis**: {analysis['description']}\n\n**Searching for**: {', '.join(analysis['queries'])}")
                    with st.expander("🛠️ Vision debug"):
                        st.markdown(f"**Media type sent to API:** `{analysis.get('media_type', 'unknown')}`")
                        st.markdown("**Raw vision model response:**")
                        st.code(analysis.get('raw_vision_response', '(none)'), language=None)

                # Always show tool call debug
                if response_data and response_data.get('tool_call_log'):
                    with st.expander("🔧 Tool calls"):
                        for call in response_data['tool_call_log']:
                            st.markdown(f"**`{call['tool']}`** — {call['duration']}")
                            st.json(call['input'])

                # Render the full response with product tables
                if response_data and 'response' in response_data:
                    for block in response_data['response']:
                        if block['type'] == 'markdown':
                            # Escape dollar signs to prevent LaTeX interpretation
                            content = block['content'].replace('$', '\\$')
                            st.markdown(content)
                        elif block['type'] == 'product_table':
                            table_data = block.get('content', {})
                            title = table_data.get('title', 'Products')
                            products = table_data.get('products', [])

                            if products:
                                st.markdown(f"### 🛍️ {title}")
                                product_ids = [p.get('id') for p in products if p.get('id')]

                                if product_ids and hasattr(st.session_state.agent, 'product_cache'):
                                    product_cache = st.session_state.agent.product_cache
                                    display_products = [product_cache.get(pid) for pid in product_ids[:6] if pid in product_cache]

                                    if display_products:
                                        num_cols = min(len(display_products), 3)
                                        cols = st.columns(num_cols)

                                        for pidx, details in enumerate(display_products):
                                            col = cols[pidx % num_cols]
                                            with col:
                                                name = details.get('name', 'Unknown Product')
                                                brand = details.get('brand', '')
                                                price = details.get('price')
                                                rating = details.get('rating')

                                                st.markdown(f"""
                                                <div style="
                                                    border: 1px solid #e0e0e0;
                                                    border-radius: 8px;
                                                    padding: 12px;
                                                    margin-bottom: 10px;
                                                    background-color: #fff;
                                                ">
                                                    <p style="margin: 0 0 4px 0; font-size: 11px; color: #999; text-transform: uppercase;">{brand}</p>
                                                    <p style="margin: 0 0 8px 0; font-weight: 600; color: #000; font-size: 14px;">{name[:50]}{'...' if len(name) > 50 else ''}</p>
                                                    <p style="margin: 0; font-size: 16px; color: #d4007a; font-weight: bold;">{'$' + str(int(price)) if price else 'Price varies'}</p>
                                                    {f'<p style="margin: 4px 0 0 0; font-size: 12px; color: #666;">⭐ {rating}</p>' if rating else ''}
                                                </div>
                                                """, unsafe_allow_html=True)

                    # Display follow-up
                    if response_data.get('follow_up'):
                        st.markdown(f"\n---\n\n❓ **{response_data['follow_up']}**")
                else:
                    # Fallback to text content
                    st.markdown(message["content"])
            else:
                # No structured response available, show text
                st.markdown(message["content"])

            assistant_message_count += 1

# Display suggestions from last response (only if no pending input)
if st.session_state.suggestions and not user_input_from_suggestion:
    st.write("**💡 Quick actions:**")
    cols = st.columns(min(len(st.session_state.suggestions), 3))
    for idx, suggestion in enumerate(st.session_state.suggestions):
        col = cols[idx % 3]
        if col.button(suggestion, key=f"sug_{idx}", use_container_width=True):
            # User clicked a suggestion - set pending and rerun
            st.session_state.pending_input = suggestion
            st.rerun()

# Input area — multimodal form (text + optional image, submitted together)
user_input = None
image_data_to_send = None

# Suggestion clicks bypass the form
if user_input_from_suggestion:
    user_input = user_input_from_suggestion
else:
    with st.form("input_form", clear_on_submit=True):
        text_col, img_col = st.columns([4, 1])
        with text_col:
            typed_text = st.text_input("Ask me about outdoor gear...", label_visibility="collapsed", placeholder="Ask me about outdoor gear...")
        with img_col:
            uploaded_file = st.file_uploader("📸", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

        # Preview image while staged
        if uploaded_file:
            st.image(uploaded_file, width=120, caption="Image ready — add a note and hit Send")

        submitted = st.form_submit_button("Send ✨", use_container_width=True)

    if submitted and (typed_text.strip() or uploaded_file):
        user_input = typed_text.strip() or "Visual search"
        if uploaded_file:
            image_data_to_send = uploaded_file.getvalue()
            st.session_state.staged_image = {"data": image_data_to_send, "name": uploaded_file.name}

if user_input:
    # For non-form paths (suggestions), no image
    if image_data_to_send is None and st.session_state.staged_image is None:
        pass  # text-only
    elif image_data_to_send is None and st.session_state.staged_image:
        image_data_to_send = st.session_state.staged_image["data"]
        st.session_state.staged_image = None
    # Add user message to history (with image bytes if provided)
    if image_data_to_send:
        st.session_state.messages.append({"role": "user", "content": user_input, "image": image_data_to_send})
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})

    # Display user message immediately
    with st.chat_message("user", avatar="👤"):
        if image_data_to_send:
            st.image(image_data_to_send, caption="Attached image", width=200)
        st.markdown(user_input)

    # Get agent response with streaming status
    with st.chat_message("assistant", avatar="🏔️"):
        with st.status("🔍 Searching NTO catalog...", expanded=True) as status:
            if image_data_to_send:
                st.write("👁️ Analyzing image with AI vision...")
                if user_input and user_input != "Visual search":
                    st.write(f"💬 Using your note: *\"{user_input}\"*")
                st.write("🔎 Creating search query...")
            else:
                st.write("🤔 Analyzing your request...")

            try:
                # Pass image to agent if uploaded
                response = st.session_state.agent.chat(user_input, image=image_data_to_send)

                status.update(label="✨ Found products!", state="complete", expanded=False)

                # Show image analysis if present
                if 'image_analysis' in response:
                    analysis = response['image_analysis']
                    st.info(f"🔍 **Image Analysis**: {analysis['description']}\n\n**Searching for**: {', '.join(analysis['queries'])}")
                    with st.expander("🛠️ Vision debug"):
                        st.markdown(f"**Media type sent to API:** `{analysis.get('media_type', 'unknown')}`")
                        st.markdown("**Raw vision model response:**")
                        st.code(analysis.get('raw_vision_response', '(none)'), language=None)

                # Always show tool call debug
                if response.get('tool_call_log'):
                    with st.expander("🔧 Tool calls"):
                        for call in response['tool_call_log']:
                            st.markdown(f"**`{call['tool']}`** — {call['duration']}")
                            st.json(call['input'])

                # Render response blocks (this is the LIVE render during initial response)
                response_text_for_history = ""

                if 'response' in response:
                    for block in response['response']:
                        if block['type'] == 'markdown':
                            # Escape dollar signs to prevent LaTeX interpretation
                            content = block['content'].replace('$', '\\$')
                            st.markdown(content)
                            response_text_for_history += block['content'] + "\n\n"
                        elif block['type'] == 'product_table':
                            # Render product table LIVE
                            table_data = block.get('content', {})
                            title = table_data.get('title', 'Products')
                            products = table_data.get('products', [])

                            if products:
                                st.markdown(f"### 🛍️ {title}")
                                product_ids = [p.get('id') for p in products if p.get('id')]

                                if product_ids:
                                    product_cache = st.session_state.agent.product_cache
                                    display_products = [product_cache.get(pid) for pid in product_ids[:6] if pid in product_cache]

                                    if display_products:
                                        num_cols = min(len(display_products), 3)
                                        cols = st.columns(num_cols)

                                        for idx, details in enumerate(display_products):
                                            col = cols[idx % num_cols]

                                            with col:
                                                name = details.get('name', 'Unknown Product')
                                                brand = details.get('brand', '')
                                                price = details.get('price')
                                                rating = details.get('rating')

                                                st.markdown(f"""
                                                <div style="
                                                    border: 1px solid #e0e0e0;
                                                    border-radius: 8px;
                                                    padding: 12px;
                                                    margin-bottom: 10px;
                                                    background-color: #fff;
                                                ">
                                                    <p style="margin: 0 0 4px 0; font-size: 11px; color: #999; text-transform: uppercase;">{brand}</p>
                                                    <p style="margin: 0 0 8px 0; font-weight: 600; color: #000; font-size: 14px;">{name[:50]}{'...' if len(name) > 50 else ''}</p>
                                                    <p style="margin: 0; font-size: 16px; color: #2e7d32; font-weight: bold;">{'$' + str(int(price)) if price else 'Price varies'}</p>
                                                    {f'<p style="margin: 4px 0 0 0; font-size: 12px; color: #666;">⭐ {rating}</p>' if rating else ''}
                                                </div>
                                                """, unsafe_allow_html=True)

                                response_text_for_history += f"\n\n**{title}** ({len(products)} products)\n"

                # Display follow-up question
                if 'follow_up' in response and response['follow_up']:
                    follow_up = response['follow_up']
                    st.markdown(f"\n---\n\n❓ **{follow_up}**")
                    response_text_for_history += f"\n\n❓ {follow_up}"

                # Store BOTH text and full structured response
                st.session_state.messages.append({"role": "assistant", "content": response_text_for_history})
                st.session_state.message_responses.append(response)  # Store full response structure

                # Update suggestions
                st.session_state.suggestions = response.get('suggestions', [])

            except Exception as e:
                status.update(label="❌ Error occurred", state="error")
                st.error(f"Error: {e}")
                import traceback
                st.code(traceback.format_exc())

    st.rerun()

# Example queries at the bottom if no messages yet
if not st.session_state.messages:
    st.divider()
    st.subheader("Try asking:")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🥾 Waterproof hiking boots"):
            st.session_state.messages.append({"role": "user", "content": "I need waterproof hiking boots for wet trails"})
            st.rerun()

    with col2:
        if st.button("🧥 Lightweight jackets"):
            st.session_state.messages.append({"role": "user", "content": "Show me lightweight packable jackets for hiking"})
            st.rerun()

    with col3:
        if st.button("🏕️ Camping gear under $100"):
            st.session_state.messages.append({"role": "user", "content": "What camping gear do you have under $100?"})
            st.rerun()
