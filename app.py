import anthropic
import streamlit as st
from dotenv import load_dotenv

# .env の ANTHROPIC_API_KEY を読み込む（キーはコードに書かない）
load_dotenv()

MODEL = "claude-opus-5-5"

# AIへの指示（要件定義書 3章・5章）
SYSTEM_PROMPT = """あなたは、仕事と子育てを両立している母親の話を聞く、やさしい聞き手です。
相手が書いたイライラした出来事から、その裏にある「本当の願い」を一緒に見つけます。

## 進め方
1. 最初の返答では、まず気持ちを受け止めて共感し、そのあと問いを1つだけ返す。
2. 相手が答えたら、短く受け止めてから次の問いを1つ返す。これを3〜4回くり返す。
3. 願いが見えてきたら「あなたは本当は〜を大切にしたかったのかもしれません」とまとめ、
   「しっくりきますか？」と本人に確かめる。違うと言われたら、問いを続けて考え直す。

## 守ること
- イライラしたことを否定しない。まず共感する。
- 問いは1回に1つだけ。短く、答えやすく。
- 説教やアドバイスをしない。「母親なのだから」「もっと〜すべき」などと言わない。
- 願いは断定せず「〜かもしれません」と提案する。
- 返答は短めに、やわらかい話し言葉で。

## 危険な兆候への対応
「消えたい」「死にたい」「子どもを叩いてしまいそう」など、本人や子どもの安全に関わる言葉が出たら、
深掘りや問いかけをやめ、気持ちを受け止めたうえで、次のような相談窓口を案内する。
- 児童相談所 虐待対応ダイヤル「189」
- よりそいホットライン
- 身近な人や医療機関に話すこと
"""

FIRST_MESSAGE = "こんにちは。最近イライラしたことを、そのまま書いてみてください。うまく書こうとしなくて大丈夫です。"


@st.cache_resource
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def ask_claude(messages: list[dict]) -> str:
    response = get_client().beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=messages,
        output_config={"effort": "low"},
        # 安全上の理由で応答が止まったとき、サーバー側で別モデルに切り替える
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return "ごめんなさい、うまくお返事できませんでした。少し言い方を変えて、もう一度書いてみてください。"
    return "".join(b.text for b in response.content if b.type == "text")


st.set_page_config(page_title="イライラから本当の願いを発見するAI", page_icon="🌱")

# ヘッダー
st.title("🌱 イライラから本当の願いを発見するAI")
st.write("イライラの奥には、あなたの大切な「願い」が隠れています。AIと話しながら一緒に見つけてみましょう。")
st.caption("※ これはセルフケアのツールで、医療やカウンセリングの代わりではありません。")

# 「新しく話す」ボタンで会話をリセット
if st.button("新しく話す"):
    st.session_state.messages = []
    st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

# これまでの会話を表示
with st.chat_message("assistant"):
    st.write(FIRST_MESSAGE)
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

# 入力欄
if prompt := st.chat_input("イライラしたことや、問いへの答えを書いてください"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("考えています…"):
                reply = ask_claude(st.session_state.messages)
        except anthropic.AuthenticationError:
            st.session_state.messages.pop()
            st.error("APIキーが正しくないようです。.env の ANTHROPIC_API_KEY を確認してください。")
            st.stop()
        except anthropic.APIError as e:
            st.session_state.messages.pop()
            st.error(f"AIとの通信でエラーが起きました。少し待ってからもう一度送ってください。（{e}）")
            st.stop()
        st.write(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
