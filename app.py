import csv
from datetime import datetime
from pathlib import Path

import anthropic
import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel

# .env の ANTHROPIC_API_KEY を読み込む（キーはコードに書かない）
load_dotenv()

MODEL = "claude-sonnet-5-5"

# 記録の保存先（個人的な内容なので .gitignore でGitHubに上げない）
RECORDS_FILE = Path(__file__).parent / "records.csv"
COLUMNS = ["日時", "場面", "イライラ度（前）", "イライラ度（後）", "出来事", "願い", "行動"]
SCENES = ["朝の支度", "食事", "寝かしつけ", "仕事", "パートナー", "その他"]
LEVELS = {1: "1 ちょっとモヤッと", 2: "2 モヤモヤ", 3: "3 イライラ", 4: "4 かなりイライラ", 5: "5 爆発しそう"}

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


# 記録用に、会話から「願い」と「行動」を決まった形で取り出すための指示
SUMMARY_PROMPT = """これから渡すのは、イライラした出来事について、本人とAIが話した会話です。
記録のために、次の2つを取り出してください。
- wish: 本人が「しっくりくる」と選んだ願い。選んでいなければ、AIが示した願いのうち中心となるもの。
  「〜を大切にしたかった」の「〜」の部分を、20〜40字程度で。願いがまだ出ていなければ空文字。
- actions: AIが提案した小さな行動を、1つ15字程度に短くしたもの。提案がなければ空のリスト。"""

FIRST_MESSAGE = "こんにちは。最近イライラしたことを、そのまま書いてみてください。うまく書こうとしなくて大丈夫です。"


class Summary(BaseModel):
    wish: str
    actions: list[str]


@st.cache_resource
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def ask_claude(messages: list[dict], scene: str) -> str:
    # 選んだ場面をAIにも伝える（画面の吹き出しには出さない）
    api_messages = [dict(m) for m in messages]
    api_messages[0]["content"] = f"（場面：{scene}）\n{api_messages[0]['content']}"
    response = get_client().beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=api_messages,
        output_config={"effort": "medium"},
        # 安全上の理由で応答が止まったとき、サーバー側で別モデルに切り替える
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return "ごめんなさい、うまくお返事できませんでした。少し言い方を変えて、もう一度書いてみてください。"
    return "".join(b.text for b in response.content if b.type == "text")


def summarize(messages: list[dict]) -> Summary:
    transcript = "\n".join(
        f"{'本人' if m['role'] == 'user' else 'AI'}：{m['content']}" for m in messages
    )
    response = get_client().messages.parse(
        model=MODEL,
        max_tokens=4000,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": transcript}],
        output_format=Summary,
    )
    return response.parsed_output or Summary(wish="", actions=[])


def save_record(row: dict) -> None:
    # Excelで文字化けしないよう、新しく作るときだけBOM付きUTF-8にする
    is_new = not RECORDS_FILE.exists()
    with open(RECORDS_FILE, "w" if is_new else "a", encoding="utf-8-sig" if is_new else "utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def load_records() -> list[dict]:
    if not RECORDS_FILE.exists():
        return []
    with open(RECORDS_FILE, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def reset_conversation() -> None:
    st.session_state.messages = []
    for key in ["scene", "before", "after", "scene_value", "before_value", "saved"]:
        st.session_state.pop(key, None)


def talk_page() -> None:
    st.title("イライラから本当の願いを発見するAI")
    st.write("イライラの奥には、あなたの大切な「願い」が隠れています。AIと話しながら一緒に見つけてみましょう。")
    st.caption("※ これはセルフケアのツールで、医療やカウンセリングの代わりではありません。")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if st.button("新しく話す"):
        reset_conversation()
        st.rerun()

    messages = st.session_state.messages

    # 話す前：場面とイライラ度を選ぶ
    if not messages:
        st.segmented_control("どんな場面でしたか？", SCENES, key="scene")
        st.select_slider(
            "今のイライラ度は？", options=list(LEVELS), value=3, format_func=LEVELS.get, key="before"
        )
    else:
        st.caption(
            f"場面：{st.session_state.scene_value}　／　話す前のイライラ度：{LEVELS[st.session_state.before_value]}"
        )

    # これまでの会話を表示
    with st.chat_message("assistant"):
        st.write(FIRST_MESSAGE)
    for m in messages:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # 話し終えたら：今のイライラ度をつけて記録する
    saved = st.session_state.get("saved")
    if len(messages) >= 2 and not saved:
        with st.container(border=True):
            st.write("**話し終えたら、今の気持ちをつけて記録しましょう**")
            st.select_slider(
                "今のイライラ度は？", options=list(LEVELS), value=st.session_state.before_value,
                format_func=LEVELS.get, key="after",
            )
            if st.button("記録して終わる", type="primary"):
                try:
                    with st.spinner("記録しています…"):
                        summary = summarize(messages)
                except anthropic.APIError as e:
                    st.error(f"記録のまとめでエラーが起きました。少し待ってからもう一度押してください。（{e}）")
                    st.stop()
                save_record({
                    "日時": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "場面": st.session_state.scene_value,
                    "イライラ度（前）": st.session_state.before_value,
                    "イライラ度（後）": st.session_state.after,
                    "出来事": messages[0]["content"],
                    "願い": summary.wish,
                    "行動": " / ".join(summary.actions),
                })
                st.session_state.saved = {
                    "before": st.session_state.before_value,
                    "after": st.session_state.after,
                    "wish": summary.wish,
                }
                st.rerun()

    if saved:
        diff = saved["before"] - saved["after"]
        change = f"{diff}下がりました" if diff > 0 else ("変わりませんでした" if diff == 0 else f"{-diff}上がりました")
        message = f"記録しました。イライラ度は {saved['before']} → {saved['after']}（{change}）。"
        if saved["wish"]:
            message += f"\n\n今日見つかった願い：{saved['wish']}"
        st.success(message)
        st.caption("「新しく話す」で次の会話を始められます。これまでの記録は上の「履歴」で見られます。")

    # 入力欄
    scene = st.session_state.get("scene") if not messages else st.session_state.scene_value
    if saved:
        placeholder = "記録しました。「新しく話す」で次の会話を始められます"
    elif not scene:
        placeholder = "まず、上で場面を選んでください"
    elif messages:
        placeholder = "答えを書いてください"
    else:
        placeholder = "イライラしたできごとを書いてください"

    if prompt := st.chat_input(placeholder, disabled=bool(saved) or not scene):
        if not messages:
            # 入力欄が消えると選んだ値も消えるため、別の場所に写しておく
            st.session_state.scene_value = st.session_state.scene
            st.session_state.before_value = st.session_state.before
        messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            try:
                with st.spinner("考えています…"):
                    reply = ask_claude(messages, st.session_state.scene_value)
            except anthropic.AuthenticationError:
                messages.pop()
                st.error("APIキーが正しくないようです。.env の ANTHROPIC_API_KEY を確認してください。")
                st.stop()
            except anthropic.APIError as e:
                messages.pop()
                st.error(f"AIとの通信でエラーが起きました。少し待ってからもう一度送ってください。（{e}）")
                st.stop()
            st.write(reply)

        messages.append({"role": "assistant", "content": reply})
        # 入力欄の案内文や記録ボタンを出すため、画面を描き直す
        st.rerun()


def history_page() -> None:
    st.title("履歴")
    records = load_records()
    if not records:
        st.info("まだ記録がありません。「話す」で会話をして、最後に「記録して終わる」を押すと、ここにたまっていきます。")
        return

    records.reverse()  # 新しい順
    avg_before = sum(int(r["イライラ度（前）"]) for r in records) / len(records)
    avg_after = sum(int(r["イライラ度（後）"]) for r in records) / len(records)
    col1, col2 = st.columns(2)
    col1.metric("記録の数", f"{len(records)}件")
    col2.metric("イライラ度の平均（話す前 → 後）", f"{avg_before:.1f} → {avg_after:.1f}")
    st.dataframe(records, hide_index=True, width="stretch")
    st.caption(f"記録は {RECORDS_FILE.name} に保存されています（Excelでも開けます）。")


st.set_page_config(page_title="イライラから本当の願いを発見するAI")

# Streamlitのページは英語扱いのため、ブラウザが日本語を「翻訳」して文字が変わってしまう。
# ページを日本語・翻訳不要として登録し直す。
st.iframe(
    """<script>
    const root = window.parent.document.documentElement;
    root.lang = "ja";
    root.setAttribute("translate", "no");
    root.classList.add("notranslate");
    </script>""",
    height=1,
)

page = st.navigation(
    [st.Page(talk_page, title="話す", default=True), st.Page(history_page, title="履歴", url_path="history")],
    position="top",
)
page.run()
