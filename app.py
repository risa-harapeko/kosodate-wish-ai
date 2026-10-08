import csv
import hmac
import io
import json
import os
import random
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import altair as alt
import anthropic
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel

# .env の ANTHROPIC_API_KEY を読み込む（キーはコードに書かない）
load_dotenv()

# ネットに公開したときの設定（Streamlit Community Cloud の Secrets に書く。手元では未設定でよい）
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")  # 設定すると、パスワードを知っている人だけが使える
# true にすると公開版の動きになる：記録は使った人のブラウザの中だけに保存し、アプリ（作者）には残さない
PUBLIC_MODE = os.environ.get("GUEST_MODE") == "true"

MODEL = "claude-sonnet-5-5"

# 記録の保存先（個人的な内容なので .gitignore でGitHubに上げない）
RECORDS_FILE = Path(__file__).parent / "records.csv"
COLUMNS = ["日時", "場面", "イライラ度（前）", "イライラ度（後）", "出来事", "願い", "願いの種類", "行動"]
# グラフで数えやすいよう、願いをこの中のどれか1つに分類する（AIへの指示の「願いの見つけ方」と同じ言葉）
WISH_CATEGORIES = [
    "休息・余白", "自由・自分のペース", "安心", "尊重", "わかってもらうこと", "つながり", "頼れること",
    "公平さ", "自分らしさ", "有能感（ちゃんとできている実感）", "楽しさ", "成長", "貢献",
]
WishCategory = Literal[
    "休息・余白", "自由・自分のペース", "安心", "尊重", "わかってもらうこと", "つながり", "頼れること",
    "公平さ", "自分らしさ", "有能感（ちゃんとできている実感）", "楽しさ", "成長", "貢献",
]
# 週のまとめの保存先（記録と同じく個人的な内容なので GitHub に上げない）
WEEKLY_FILE = Path(__file__).parent / "weekly_summaries.json"
WEEKDAYS = "月火水木金土日"
BAR_COLOR = "#A85A3A"  # ボタンと同じテラコッタ
TEXT_COLOR = "#4A3F35"
GRID_COLOR = "#E8DFD3"
SCENES = ["朝の支度", "食事", "寝かしつけ", "仕事", "パートナー", "その他"]
LEVELS = {1: "1 ちょっとモヤッと", 2: "2 モヤモヤ", 3: "3 イライラ", 4: "4 かなりイライラ", 5: "5 爆発しそう"}
# 話したあとは、いちばん軽い「1」を「すっきりした！」と表す（数字の意味は同じ）
LEVELS_AFTER = {**LEVELS, 1: "1 すっきりした！"}

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
事実確認（「何時に起きましたか？」）ではなく、本人が自分では考えたことのない角度の問いを選ぶ。
- 相手の話に出てきた具体的な言葉や場面（「お迎えのとき」「LINEの一言」など）に触れてから問う。
  どの相談にもそのまま使える、決まり文句のような問いにしない。
- 会話の最初に「今回の問いの切り口」が渡される。話の内容に合うものを選び、言い回しは自分の言葉にする。
  合うものがなければ、別の角度を考えてよい。
- 2回目の問いは、1回目と違う切り口にする。

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
   - 行動を提案したこの返答に限り、最後の行に [END] とだけ書く（アプリが記録の案内を出す合図で、本人には表示されない）。

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
- 児童相談所 虐待対応ダイヤル「189」（24時間・通話料無料）
- よりそいホットライン 0120-279-338（24時間・通話料無料）
- 身近な人や医療機関に話すこと
"""


# 記録用に、会話から「願い」と「行動」を決まった形で取り出すための指示
SUMMARY_PROMPT = """これから渡すのは、イライラした出来事について、本人とAIが話した会話です。
記録のために、次の3つを取り出してください。
- wish: 本人が「しっくりくる」と選んだ願い。選んでいなければ、AIが示した願いのうち中心となるもの。
  「〜を大切にしたかった」の「〜」の部分だけを、20〜40字程度の名詞の形で（例：「頑張りをわかってもらえること」）。
  「を大切にしたかった」は含めない。願いがまだ出ていなければ空文字。
- category: wish にいちばん近い願いの種類を、選択肢から1つ。
- actions: AIが提案した小さな行動を、1つ15字程度に短くしたもの。提案がなければ空のリスト。"""

# 週の記録から、傾向と対策をまとめるための指示
WEEKLY_PROMPT = """あなたは、仕事と子育てを両立している母親の「イライラの記録」を一緒にふりかえる、やさしい伴走者です。
これから、ある1週間の記録を渡します。各記録には、日時（曜日）・場面・話す前と後のイライラ度（1〜5）・
出来事・見つかった願い・願いの種類・AIが提案した行動が入っています。

次の見出しで、短くまとめてください（全体で400〜600字程度、やわらかい話し言葉で）。

### 今週のふりかえり
記録の数と、話す前と後でイライラ度がどう変わったかを、ねぎらいの言葉とともに。

### イライラしやすかった場面・曜日・時間帯
記録から読み取れる傾向。記録が少なく傾向と言えない項目は、無理に言わず「まだわからない」とする。

### くり返し出てきた願い
願いの種類や言葉の共通点から、本人が大切にしていることを「〜かもしれません」と伝える。

### 来週ためせる小さなこと
傾向と願いにつながる、小さな行動を2〜3個。「休む」「手放す」「頼る」「伝える」方向のものにし、
頑張りを増やす行動（早起き・もっと計画的に など）は入れない。やらなくてもいい前提で伝える。

守ること：説教しない。「母親なのだから」「〜すべき」と言わない。本人や家族を評価・批判しない。
記録に「消えたい」「子どもを叩いてしまいそう」など安全に関わる内容があれば、まとめより先に気持ちを受け止め、
児童相談所 虐待対応ダイヤル「189」やよりそいホットライン 0120-279-338（どちらも24時間・無料）を案内する。"""

# 問いの切り口。毎回同じような問いにならないよう、会話ごとにこの中から4つを選んでAIに渡す
QUESTION_ANGLES = [
    "心の声：そのとき、心の中でどんな言葉がよぎっていたか",
    "体の感覚：そのとき、体のどこに力が入っていたか、どんな感じがしたか",
    "例外：同じことが起きてもイライラしない日はあるか、その日は何が違うか",
    "理想の場面：その場面が思いどおりにいったら、どんな様子だったか",
    "ほしかった一言：相手から、本当はどんな一言がほしかったか",
    "言いたかった一言：何を言っても大丈夫だとしたら、相手に何と言いたかったか",
    "友だちの目：同じことを友だちが話してくれたら、その友だちに何と声をかけるか",
    "守りたかったもの：その場面で、いちばん守りたかったものは何か",
    "奪われた感じ：その出来事で、いちばん奪われた感じがしたもの（時間・気持ち・ペースなど）は何か",
    "くり返し：前にも似たイライラがあったか、そのときとの共通点は何か",
    "余裕：もしその日あと30分余裕があったら、同じ場面はどう違っていたか",
    "役割：そのとき「母」「妻」「働く自分」「ひとりの自分」のどの気持ちが強かったか",
    "たとえ：そのときの気持ちを天気や色にたとえると何か",
    "未来の自分：1年後の自分がこの場面を見たら、今の自分に何と言いそうか",
    "子どもの頃：子どもの頃、似た場面で誰かにしてほしかったことはあるか",
    "魔法：それが魔法のように解決したら、浮いた時間や気持ちで何をしたいか",
]

END_MARK = "[END]"  # AIが会話を締めくくったときの合図

FIRST_MESSAGE ="こんにちは。最近イライラしたことを、そのまま書いてみてください。うまく書こうとしなくて大丈夫です。"


class Summary(BaseModel):
    wish: str
    category: WishCategory
    actions: list[str]


class Categories(BaseModel):
    categories: list[WishCategory]


@st.cache_resource
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def ask_claude(messages: list[dict], scene: str, angles: list[str]) -> str:
    # 選んだ場面と今回の問いの切り口をAIにも伝える（画面の吹き出しには出さない）
    # APIには役割と本文だけを渡す（"final" などアプリ用の情報は渡さない）
    api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    angle_text = "\n".join(f"- {a}" for a in angles)
    api_messages[0]["content"] = (
        f"（場面：{scene}）\n（今回の問いの切り口：\n{angle_text}）\n{api_messages[0]['content']}"
    )
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
    summary = response.parsed_output
    if summary is None:  # AIが答えられなかったときは空のまま記録する
        return Summary.model_construct(wish="", category="", actions=[])
    summary.wish = clean_wish(summary.wish)
    return summary


def clean_wish(wish: str) -> str:
    # グラフで同じ願いを数えやすいよう、書き方をそろえる
    for tail in ["を大切にしたかった", "を大切にしたい", "。"]:
        wish = wish.removesuffix(tail)
    return wish.strip()


def classify_wishes(wishes: list[str]) -> list[str]:
    # 「願いの種類」がまだない古い記録を、まとめて分類する
    response = get_client().messages.parse(
        model=MODEL,
        max_tokens=4000,
        system="渡す願いのそれぞれについて、いちばん近い願いの種類を選択肢から1つ選び、同じ順番で返してください。",
        messages=[{"role": "user", "content": "\n".join(f"{i + 1}. {w}" for i, w in enumerate(wishes))}],
        output_format=Categories,
    )
    result = response.parsed_output
    if result is None or len(result.categories) != len(wishes):
        return [""] * len(wishes)
    return list(result.categories)


def write_records(records: list[dict]) -> None:
    if PUBLIC_MODE:
        st.session_state.browser_records = records
        return
    # Excelで文字化けしないよう、BOM付きUTF-8で書く
    with open(RECORDS_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def save_record(row: dict) -> None:
    # 項目が増えても古い記録とずれないよう、毎回すべて書き直す（記録は多くても数百件なので十分速い）
    write_records(load_records() + [row])


def load_records() -> list[dict]:
    if PUBLIC_MODE:
        records = [dict(r) for r in st.session_state.get("browser_records", [])]
    elif not RECORDS_FILE.exists():
        return []
    else:
        with open(RECORDS_FILE, encoding="utf-8-sig", newline="") as f:
            records = list(csv.DictReader(f))
    for r in records:  # あとから増えた項目は空にしておく
        for col in COLUMNS:
            r[col] = r.get(col) or ""
    return records


# 公開版の記録は、使った人のブラウザ（localStorage）に保存する。サーバーやアプリの作者には残らない
BROWSER_STORE_JS = """
export default function(component) {
    const { data, setStateValue } = component;
    if (data.write !== null) {
        localStorage.setItem(data.key, data.write);
    }
    setStateValue("value", localStorage.getItem(data.key) ?? "");
}
"""
_browser_store = st.components.v2.component("browser_store", js=BROWSER_STORE_JS)


def browser_store(name: str, content) -> str | None:
    # content を渡すとブラウザに書き込み、ブラウザに今ある中身を返す（読み込み前は None）
    write = None if content is None else json.dumps(content, ensure_ascii=False)
    result = _browser_store(
        key=f"store_{name}",
        data={"key": f"kosodate_{name}_v1", "write": write},
        default={"value": None},
        on_value_change=lambda: None,
    )
    return result.value


def sync_browser_storage() -> None:
    loaded = st.session_state.get("browser_loaded", False)
    records = browser_store("records", st.session_state.browser_records if loaded else None)
    weekly = browser_store("weekly", st.session_state.browser_weekly if loaded else None)
    if not loaded:
        if records is None or weekly is None:
            st.caption("記録を読み込んでいます…")
            st.stop()
        st.session_state.browser_records = json.loads(records) if records else []
        st.session_state.browser_weekly = json.loads(weekly) if weekly else {}
        st.session_state.browser_loaded = True
        st.rerun()


def records_to_csv(records: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue().encode("utf-8-sig")  # Excelで文字化けしないようBOM付き


def week_start(date_text: str) -> str:
    # 記録の日時から、その週の月曜日の日付を返す
    day = datetime.strptime(date_text, "%Y-%m-%d %H:%M")
    return (day - timedelta(days=day.weekday())).strftime("%Y-%m-%d")


def week_label(start: str) -> str:
    first = datetime.strptime(start, "%Y-%m-%d")
    last = first + timedelta(days=6)
    return f"{first:%m/%d}（月）〜 {last:%m/%d}（日）の週"


def load_weekly() -> dict:
    if PUBLIC_MODE:
        return dict(st.session_state.get("browser_weekly", {}))
    if not WEEKLY_FILE.exists():
        return {}
    return json.loads(WEEKLY_FILE.read_text(encoding="utf-8"))


def save_weekly(start: str, text: str) -> None:
    weekly = load_weekly()
    weekly[start] = text
    if PUBLIC_MODE:
        st.session_state.browser_weekly = weekly
        return
    WEEKLY_FILE.write_text(json.dumps(weekly, ensure_ascii=False, indent=2), encoding="utf-8")


def make_weekly_summary(records: list[dict]) -> str:
    lines = []
    for r in records:
        day = datetime.strptime(r["日時"], "%Y-%m-%d %H:%M")
        lines.append(
            f"- {r['日時']}（{WEEKDAYS[day.weekday()]}）／場面：{r['場面']}／イライラ度：{r['イライラ度（前）']}→{r['イライラ度（後）']}"
            f"／出来事：{r['出来事']}／願い：{r['願い']}（{r['願いの種類']}）／提案された行動：{r['行動']}"
        )
    # 件数や平均はAIに数えさせず、計算した値を渡す
    before = [int(r["イライラ度（前）"]) for r in records]
    after = [int(r["イライラ度（後）"]) for r in records]
    facts = (
        f"記録の数：{len(records)}件\n"
        f"イライラ度の平均：話す前 {sum(before) / len(before):.1f} → 話した後 {sum(after) / len(after):.1f}\n"
        f"話して下がった記録：{sum(1 for b, a in zip(before, after) if a < b)}件\n"
        f"場面ごとの件数：{'、'.join(f'{k} {v}件' for k, v in Counter(r['場面'] for r in records).most_common())}\n"
        "（数字はこの値をそのまま使うこと）\n\n記録：\n"
    )
    response = get_client().beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=WEEKLY_PROMPT,
        messages=[{"role": "user", "content": facts + "\n".join(lines)}],
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return "ごめんなさい、今回はうまくまとめられませんでした。時間をおいて、もう一度ためしてみてください。"
    return "".join(b.text for b in response.content if b.type == "text")


def bar_chart(counts: Counter, label: str) -> alt.Chart:
    # 横向きの棒グラフ（多い順）。棒の先だけ角を丸め、目盛りの線は控えめにする
    df = pd.DataFrame(counts.most_common(), columns=[label, "件数"])
    return (
        alt.Chart(df)
        .mark_bar(color=BAR_COLOR, cornerRadiusEnd=4, size=16)
        .encode(
            x=alt.X("件数:Q", title=None, axis=alt.Axis(tickMinStep=1, format="d", gridColor=GRID_COLOR,
                                                       domain=False, ticks=False, labelColor=TEXT_COLOR)),
            y=alt.Y(f"{label}:N", sort="-x", title=None,
                    axis=alt.Axis(domain=False, ticks=False, labelColor=TEXT_COLOR, labelLimit=220, labelFontSize=13)),
            tooltip=[alt.Tooltip(f"{label}:N"), alt.Tooltip("件数:Q")],
        )
        .properties(height=max(90, 34 * len(df)))
        .configure_view(stroke=None)
        .configure(background="transparent")
    )


def reset_conversation() -> None:
    st.session_state.messages = []
    for key in ["scene", "before", "after", "scene_value", "before_value", "saved", "angles"]:
        st.session_state.pop(key, None)


def talk_page() -> None:
    st.title("イライラから本当の願いを発見するAI")
    st.write("イライラの奥には、あなたの大切な「願い」が隠れています。AIと話しながら一緒に見つけてみましょう。")
    st.caption("※ これはセルフケアのツールで、医療やカウンセリングの代わりではありません。")
    if PUBLIC_MODE:
        st.caption(
            "※ 書いた内容は、返事を作るためにAI（Anthropic社のClaude）に送られます。"
            "記録はこの端末のブラウザの中だけに保存され、アプリの作者を含め他の人は見られません。"
            "お名前など、個人が特定できることは書かないでください。"
        )

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
    # 願いのまとめと行動の提案が終わってから（AIが [END] の合図を出してから）表示する
    # 合図が出ないまま長く続いたときも記録できるよう、5往復を超えたら表示する
    concluded = any(m.get("final") for m in messages) or len(messages) >= 10
    if concluded and not saved:
        with st.container(border=True):
            st.write("**話し終えたら、今の気持ちをつけて記録しましょう**")
            st.select_slider(
                "今のイライラ度は？", options=list(LEVELS_AFTER), value=st.session_state.before_value,
                format_func=LEVELS_AFTER.get, key="after",
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
                    "願いの種類": summary.category,
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

    # 相談先は、会話のじゃまにならないよう画面の下に置く
    with st.expander("つらいときの相談先"):
        st.markdown(
            "- 児童相談所 虐待対応ダイヤル **189**（24時間・通話料無料・匿名可）\n"
            "- よりそいホットライン **0120-279-338**（24時間・通話料無料）"
        )

    # 入力欄
    scene = st.session_state.get("scene") if not messages else st.session_state.scene_value
    if saved:
        placeholder = "「新しく話す」で次の会話を始められます"
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
            st.session_state.angles = random.sample(QUESTION_ANGLES, 4)
        messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            try:
                with st.spinner("考えています…"):
                    reply = ask_claude(messages, st.session_state.scene_value, st.session_state.angles)
            except anthropic.AuthenticationError:
                messages.pop()
                st.error("APIキーが正しくないようです。.env の ANTHROPIC_API_KEY を確認してください。")
                st.stop()
            except anthropic.APIError as e:
                messages.pop()
                st.error(f"AIとの通信でエラーが起きました。少し待ってからもう一度送ってください。（{e}）")
                st.stop()
            final = END_MARK in reply
            reply = reply.replace(END_MARK, "").strip()
            st.write(reply)

        messages.append({"role": "assistant", "content": reply, "final": final})
        # 入力欄の案内文や記録ボタンを出すため、画面を描き直す
        st.rerun()


def history_page() -> None:
    st.title("履歴")
    records = load_records()
    if not records:
        st.info("まだ記録がありません。「話す」で会話をして、最後に「記録して終わる」を押すと、ここにたまっていきます。")
    else:
        avg_before = sum(int(r["イライラ度（前）"]) for r in records) / len(records)
        avg_after = sum(int(r["イライラ度（後）"]) for r in records) / len(records)
        col1, col2 = st.columns(2)
        col1.metric("記録の数", f"{len(records)}件")
        col2.metric("イライラ度の平均（話す前 → 後）", f"{avg_before:.1f} → {avg_after:.1f}")
        st.dataframe(records[::-1], hide_index=True, width="stretch")  # 新しい順
        st.download_button(
            "記録をダウンロード（バックアップ）", records_to_csv(records),
            file_name=f"irairadiary_{datetime.now():%Y%m%d}.csv", mime="text/csv",
        )

    if PUBLIC_MODE:
        st.caption(
            "記録はこの端末のブラウザの中だけに保存されています。アプリの作者を含め、他の人は見られません。"
            "ブラウザのデータを消したり、機種変更したりすると記録も消えるので、ときどきダウンロードしておくと安心です。"
        )
        with st.expander("バックアップから記録を戻す"):
            uploaded = st.file_uploader("ダウンロードした記録のファイル（.csv）を選んでください", type="csv")
            if uploaded is not None and st.button("この記録を戻す"):
                restored = list(csv.DictReader(io.StringIO(uploaded.getvalue().decode("utf-8-sig"))))
                # 同じ記録が二重にならないよう、日時と出来事が同じものは1つにまとめる
                merged = {(r["日時"], r["出来事"]): r for r in records + restored}
                write_records(sorted(merged.values(), key=lambda r: r["日時"]))
                st.rerun()  # 画面を描き直すと、ブラウザにも保存される
    elif records:
        st.caption(f"記録は {RECORDS_FILE.name} に保存されています（Excelでも開けます）。")


def review_page() -> None:
    st.title("ふりかえり")
    records = load_records()
    if not records:
        st.info("まだ記録がありません。記録がたまると、ここでイライラしやすい場面やよく出る願いが見られます。")
        return

    # 「願いの種類」がない古い記録があれば、先にまとめて分類しておく
    missing = [r for r in records if r["願い"] and not r["願いの種類"]]
    if missing:
        for r in records:
            r["願い"] = clean_wish(r["願い"])
        with st.spinner("これまでの記録の願いを分類しています…"):
            for r, category in zip(missing, classify_wishes([r["願い"] for r in missing])):
                r["願いの種類"] = category
        write_records(records)

    # 全体の数字
    before = [int(r["イライラ度（前）"]) for r in records]
    after = [int(r["イライラ度（後）"]) for r in records]
    lowered = sum(1 for b, a in zip(before, after) if a < b)
    col1, col2, col3 = st.columns(3)
    col1.metric("記録の数", f"{len(records)}件")
    col2.metric("イライラ度の平均", f"{sum(before) / len(before):.1f} → {sum(after) / len(after):.1f}")
    col3.metric("話して軽くなった", f"{lowered} / {len(records)}件")

    # グラフ
    st.subheader("イライラしやすい場面")
    st.altair_chart(bar_chart(Counter(r["場面"] for r in records), "場面"), width="stretch")
    st.subheader("よく出てくる願い")
    categories = Counter(r["願いの種類"] for r in records if r["願いの種類"])
    if categories:
        st.altair_chart(bar_chart(categories, "願いの種類"), width="stretch")
        with st.expander("願いの言葉を見る"):
            for category, _ in categories.most_common():
                st.markdown(f"**{category}**")
                for r in records:
                    if r["願いの種類"] == category:
                        st.markdown(f"- {r['願い']}（{r['場面']}）")

    # 週のまとめ
    st.subheader("週のまとめ")
    weeks = sorted({week_start(r["日時"]) for r in records}, reverse=True)
    start = st.selectbox("どの週をふりかえりますか？", weeks, format_func=week_label)
    week_records = [r for r in records if week_start(r["日時"]) == start]
    st.caption(f"この週の記録：{len(week_records)}件")
    saved = load_weekly().get(start)
    if saved:
        st.markdown(saved)
    if st.button("まとめを作り直す" if saved else "この週のまとめを作る", type="secondary" if saved else "primary"):
        try:
            with st.spinner("この週の記録を読んでいます…"):
                text = make_weekly_summary(week_records)
        except anthropic.APIError as e:
            st.error(f"AIとの通信でエラーが起きました。少し待ってからもう一度押してください。（{e}）")
            st.stop()
        save_weekly(start, text)
        st.rerun()


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

# パスワードが設定されているときは、正しいパスワードを入れた人だけが使える
if APP_PASSWORD and not st.session_state.get("authenticated"):
    st.title("イライラから本当の願いを発見するAI")
    with st.form("login"):
        password = st.text_input("パスワードを入力してください", type="password")
        submitted = st.form_submit_button("OK", type="primary")
    if submitted:
        if hmac.compare_digest(password, APP_PASSWORD):
            st.session_state.authenticated = True
            st.rerun()
        st.error("パスワードが違います。")
    st.stop()

pages = [st.Page(talk_page, title="話す", default=True)]
pages.append(st.Page(history_page, title="履歴", url_path="history"))
pages.append(st.Page(review_page, title="ふりかえり", url_path="review"))

if PUBLIC_MODE:
    sync_browser_storage()
page = st.navigation(
    pages,
    position="top" if len(pages) > 1 else "hidden",
)
page.run()
