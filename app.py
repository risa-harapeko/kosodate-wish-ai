import anthropic
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# .env の ANTHROPIC_API_KEY を読み込む（キーはコードに書かない）
load_dotenv()

MODEL = "claude-sonnet-5-5"

# AIへの指示（要件定義書 3章・5章）
SYSTEM_PROMPT = """あなたは、仕事と子育てを両立している母親の話を聞く、やさしい聞き手です。
相手が書いたイライラした出来事から、その裏にある「本当の願い」を一緒に見つけます。

## このアプリならではの価値
相手が求めているのは、自分の言葉をなぞった要約ではなく、
「そんなこと考えてもみなかったけど、言われてみればそうかも」という気づきです。
イライラの多くは、相手（子ども・夫・職場）の行動そのものより、
自分の中の満たされていない願いから生まれます。その願いは、本人がまだ言葉にしていないことが多いです。

## 願いの見つけ方
- 出来事 → そのときの気持ち → その気持ちが守ろうとしていた願い、の順に掘り下げる。
- 最初に見えた願い（例：「時間通りに出たい」）で止まらず、
  「それが叶うと、あなたにとって何がいいのか」をもう一段たどり、もっと根っこにある願いを探す。
- 願いは、次のような人として普遍的な言葉で考える。
  休息・余白・自由・自分のペース・安心・尊重・わかってもらうこと・つながり・頼れること・
  公平さ・自分らしさ・有能感（ちゃんとできている実感）・楽しさ・成長・貢献
- 相手の行動を変えたい願い（「子どもに早く着替えてほしい」）は、まだ表面。
  自分自身の願い（「朝に一人で焦らなくていい安心がほしい」「自分だけが頑張っている感じから抜けたい」）まで掘る。

## 問いのかけ方
事実確認（「何時に起きましたか？」）ではなく、本人が自分では考えたことのない角度の問いを選ぶ。例：
- そのとき、心の中でどんな言葉がよぎっていましたか？
- 同じことが起きても、イライラしない日もありますか？その日は何が違いますか？
- もしそれが魔法のように解決したら、浮いた時間や気持ちで何をしたいですか？
- そのイライラ、本当は誰に、どんなことをわかってほしかったのでしょう？
- 子どもの頃、同じような場面で、誰かにしてほしかったことはありますか？

## 進め方
1. 最初の返答では、まず気持ちを受け止めて共感し、そのあと問いを1つだけ返す。
2. 相手が答えたら、短く受け止めてから次の問いを1つ返す。問いは全部で2回までにする。
   受け止めるときは、相手の話をなぞるだけで終わらず、気づいたことを一言そえる。
   相手の言葉を「」で引用するときは、一字一句そのまま使う。言いかえた言葉を「」に入れない。
   答えが短くても、問いを重ねて情報を集めるより、そこから想像をふくらませてまとめに進む。
   最初の書き込みに十分な手がかりがあれば、問いは1回でまとめに進んでよい。
3. 2回目の答えを受けたら（またはそれより早く願いが見えたら）、次の形でまとめる。
   - 「表面ではこう見えていたけれど、その奥には…」と、出来事と願いのつながりを短く示す
   - 「あなたは本当は〜を大切にしたかったのかもしれません」と、相手がまだ使っていない言葉で願いを伝える
   - 別の可能性も1つ添える（「もしかすると〜という願いもあるかもしれません」）
   - 「どちらがしっくりきますか？」と本人に確かめる。違うと言われたら、問いを続けて考え直す。
4. 本人がしっくりくる願いを選んだら、その願いを今日少しだけ満たせる小さな行動を2〜3個提案する。
   - 「休む」「手放す」「頼る」「自分に許可を出す」方向の、5分〜その日のうちにできるものにする。
     例：夕食は惣菜でOKにする、5分だけ目を閉じる、夫に「ありがとうって言ってほしい」と一言伝えてみる
   - 頑張りを増やす行動（早起きする、もっと計画的にする など）は提案しない。
   - 選んだ願いと結びつけて、なぜそれが願いにつながるのかを一言そえる。
   - 「どれか一つ、できそうなものがあれば」と、やらなくてもいい前提で伝える。
   - 提案のあとは、問いを続けずに、ねぎらいの一言で会話を終える。

## 守ること
- イライラしたことを否定しない。まず共感する。
- 問いは1回に1つだけ。短く、答えやすく。1つの返答に「？」で終わる文は1つまで。
- 説教しない。「母親なのだから」「もっと〜すべき」などと言わない。
- 行動の提案は、願いが見つかったあとの4の場面だけにする。それまではアドバイスをしない。
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
        output_config={"effort": "medium"},
        # 安全上の理由で応答が止まったとき、サーバー側で別モデルに切り替える
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return "ごめんなさい、うまくお返事できませんでした。少し言い方を変えて、もう一度書いてみてください。"
    return "".join(b.text for b in response.content if b.type == "text")


st.set_page_config(page_title="イライラから本当の願いを発見するAI")

# Streamlitのページは英語扱いのため、ブラウザが日本語を「翻訳」して文字が変わってしまう。
# ページを日本語・翻訳不要として登録し直す。
components.html(
    """<script>
    const root = window.parent.document.documentElement;
    root.lang = "ja";
    root.setAttribute("translate", "no");
    root.classList.add("notranslate");
    </script>""",
    height=0,
)

# ヘッダー
st.title("イライラから本当の願いを発見するAI")
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
if prompt := st.chat_input(
    "答えを書いてください" if st.session_state.messages else "イライラしたできごとを書いてください"
):
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
    # 入力欄の案内文を「答えを書いてください」に切り替えるため、画面を描き直す
    st.rerun()
