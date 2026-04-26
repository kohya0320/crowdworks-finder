from flask import Flask, render_template, jsonify, request
import requests as http_requests
import re
import time
import os
from datetime import datetime

app = Flask(__name__)

# 結果格納
_jobs_data = {cat: [] for cat in ["script", "ai_data", "sns_bot", "data_transform"]}
_is_loading = False
_last_updated = None
_scrape_log = []
CACHE_TTL = 30 * 60

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# カテゴリ定義 & 星付け条件
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORIES = {
    "script": {
        "name": "自動化・スクリプト",
        "icon": "🤖",
        "description": "Python・GAS・RPAで自動化できる開発系タスク",
        "search_keywords": ["Python 自動化", "GAS スクリプト", "スクレイピング", "RPA"],
        "subcategories": {
            "Python自動化": {
                "keywords": ["python", "パイソン"],
                "score": 5,
                "tip": "得意領域。即提案できる。",
                "star_reason": "⭐⭐⭐⭐⭐：Pythonスクリプトで完全自動化。最も狙い目。"
            },
            "GAS・スプレッドシート連携": {
                "keywords": ["gas", "google apps script", "スプレッドシート 連携", "スプレッドシート自動"],
                "score": 5,
                "tip": "GASで完結。Claude Codeとの親和性が高い。",
                "star_reason": "⭐⭐⭐⭐⭐：GASはClaude Codeで高速実装できる最適タスク。"
            },
            "スクレイピング・データ収集": {
                "keywords": ["スクレイピング", "クローリング", "データ収集", "自動収集"],
                "score": 5,
                "tip": "BeautifulSoup/Playwrightで対応。",
                "star_reason": "⭐⭐⭐⭐⭐：スクレイピングはPythonの基本。即対応可能。"
            },
            "RPA・業務自動化": {
                "keywords": ["rpa", "業務効率化", "業務自動化", "一括作成", "一括登録"],
                "score": 4,
                "tip": "Python代替提案が競合少なく高単価になりやすい。",
                "star_reason": "⭐⭐⭐⭐：ツール指定があってもPython代替を提案すると差別化できる。"
            },
            "API連携": {
                "keywords": ["api連携", "api 連携", "webhook", "zapier", "make"],
                "score": 4,
                "tip": "requestsライブラリで実装。各種SaaS対応。",
                "star_reason": "⭐⭐⭐⭐：API仕様が公開されていれば高速実装可能。"
            },
        }
    },
    "ai_data": {
        "name": "AI・データ処理",
        "icon": "🧠",
        "description": "ChatGPT/Claude APIや機械学習で自動化できるタスク",
        "search_keywords": ["ChatGPT API", "OpenAI", "文字起こし 自動", "画像収集"],
        "subcategories": {
            "ChatGPT・AI API活用": {
                "keywords": ["chatgpt", "gpt", "openai", "claude", "ai api", "llm"],
                "score": 5,
                "tip": "API実装が得意領域。高単価狙い目。",
                "star_reason": "⭐⭐⭐⭐⭐：AI APIの実装はClaude Codeで最速対応できる。"
            },
            "文字起こし自動化": {
                "keywords": ["文字起こし 自動", "whisper", "音声認識 自動", "書き起こし 自動"],
                "score": 5,
                "tip": "Whisper APIで完全自動化。",
                "star_reason": "⭐⭐⭐⭐⭐：OpenAI Whisper APIで音声→テキスト完全自動化。"
            },
            "画像・動画処理": {
                "keywords": ["画像収集", "画像変換", "画像処理", "動画 自動", "サムネイル 自動"],
                "score": 4,
                "tip": "Pillow/FFmpegで自動バッチ処理。",
                "star_reason": "⭐⭐⭐⭐：バッチ処理スクリプトで大量ファイルを自動変換。"
            },
            "データ分析・集計": {
                "keywords": ["データ分析", "集計 自動", "レポート 自動", "pandas", "可視化"],
                "score": 4,
                "tip": "pandas+Pythonで自動集計・レポート生成。",
                "star_reason": "⭐⭐⭐⭐：pandasで自動集計→グラフ生成まで全自動化可能。"
            },
        }
    },
    "sns_bot": {
        "name": "SNS・Bot自動化",
        "icon": "📣",
        "description": "自動投稿・LINE Bot・競合リサーチなど反復SNS作業",
        "search_keywords": ["自動投稿", "LINE Bot", "競合リサーチ"],
        "subcategories": {
            "LINE Bot・自動応答": {
                "keywords": ["line bot", "linebot", "公式ライン 自動", "line 自動応答", "チャットボット"],
                "score": 5,
                "tip": "LINE Messaging APIで完全自動化。",
                "star_reason": "⭐⭐⭐⭐⭐：LINE APIで自動応答Bot。Claude Codeで高速実装可。"
            },
            "SNS自動投稿": {
                "keywords": ["自動投稿", "instagram 自動", "x 自動", "twitter 自動", "youtube 自動"],
                "score": 5,
                "tip": "各SNS公式APIで自動投稿スクリプト実装。",
                "star_reason": "⭐⭐⭐⭐⭐：API経由の自動投稿はPythonで完全自動化できる。"
            },
            "競合リサーチ・価格調査": {
                "keywords": ["競合リサーチ", "競合調査", "価格調査", "価格監視", "相場調査"],
                "score": 4,
                "tip": "スクレイピング+定期実行で自動監視。",
                "star_reason": "⭐⭐⭐⭐：定期スクレイピング+通知で価格監視を完全自動化。"
            },
            "Webフォーム・DM自動送信": {
                "keywords": ["dm 自動", "メール 自動", "フォーム 自動", "問い合わせ 自動"],
                "score": 4,
                "tip": "Selenium+テンプレートで自動送信。",
                "star_reason": "⭐⭐⭐⭐：テンプレ文+自動送信スクリプトで効率化。"
            },
        }
    },
    "data_transform": {
        "name": "データ整理・変換",
        "icon": "📊",
        "description": "CSV・スプレッドシート・一括処理など構造化データの自動変換",
        "search_keywords": ["スプレッドシート 連携", "CSV 変換", "一括作成"],
        "subcategories": {
            "CSV・Excel自動処理": {
                "keywords": ["csv 処理", "csv 変換", "csv 自動", "excel 自動", "エクセル 自動", "一括変換"],
                "score": 5,
                "tip": "pandasで数行のコードで完結。最速納品できる。",
                "star_reason": "⭐⭐⭐⭐⭐：pandasでCSV/Excel処理は最も得意な領域。"
            },
            "スプレッドシート自動化": {
                "keywords": ["スプレッドシート", "google sheets", "gスプレッド", "シート 自動"],
                "score": 5,
                "tip": "GAS or Python gspreadで完全自動化。",
                "star_reason": "⭐⭐⭐⭐⭐：GAS/gspreadでスプレッドシート操作を完全自動化。"
            },
            "一括登録・一括作成": {
                "keywords": ["一括登録", "一括作成", "一括入力", "一括更新", "バッチ処理"],
                "score": 4,
                "tip": "スクリプトでループ処理→全自動。",
                "star_reason": "⭐⭐⭐⭐：繰り返し処理はスクリプトで全自動化できる。"
            },
            "データ整形・クレンジング": {
                "keywords": ["データ整形", "データ整理", "クレンジング", "名寄せ", "重複削除"],
                "score": 4,
                "tip": "pandasで自動整形。件数が多いほど価値が高い。",
                "star_reason": "⭐⭐⭐⭐：pandasで自動整形→納品。件数×単価で高収益になりやすい。"
            },
        }
    }
}


CLOSED_KEYWORDS = ["受付終了", "募集終了", "応募終了", "締め切り済", "終了しました", "受付を終了"]

# ★4未満は表示しない
MIN_SCORE = 4

# 除外キーワード（これがあれば非表示）
EXCLUDE_KEYWORDS = [
    "ai禁止", "chatgpt禁止", "aiツール不可", "ai不可", "ai使用禁止",
    "スマホのみ", "スマホ限定", "pc不可",
]

def score_job(title, description, category_key):
    text = (title + " " + description).lower()
    category = CATEGORIES[category_key]
    best_score = 0
    best_sub = "その他"
    best_tip = ""
    best_reason = ""

    for sub_name, sub_data in category["subcategories"].items():
        matches = sum(1 for kw in sub_data["keywords"] if kw in text)
        if matches > 0 and sub_data["score"] > best_score:
            best_score = sub_data["score"]
            best_sub = sub_name
            best_tip = sub_data["tip"]
            best_reason = sub_data.get("star_reason", "")

    return best_score, best_sub, best_tip, best_reason


def scrape_crowdworks(keyword, pages=3):
    """Jina AI Reader経由でCrowdWorksをスクレイピング（複数ページ対応）"""
    import urllib.parse
    jobs_raw = []
    seen_ids = set()

    headers = {
        "Accept": "text/plain",
        "User-Agent": "Mozilla/5.0",
    }
    jina_key = os.environ.get("JINA_API_KEY", "")
    if jina_key:
        headers["Authorization"] = f"Bearer {jina_key}"

    for page in range(1, pages + 1):
        cw_url = f"https://crowdworks.jp/public/jobs/search?job_type=fixed&order=new&page={page}&search[keyword]={urllib.parse.quote(keyword)}"
        jina_url = f"https://r.jina.ai/{cw_url}"
        try:
            res = http_requests.get(jina_url, headers=headers, timeout=(10, 25))
            res.encoding = "utf-8"
            text = res.text

            links = re.findall(
                r'\[([^\]]{5,})\]\(https://crowdworks\.jp/public/jobs/(\d+)[^\)]*\)',
                text
            )

            for title, job_id in links:
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                title = title.strip()
                if not title or len(title) < 5:
                    continue

                href = f"https://crowdworks.jp/public/jobs/{job_id}"

                idx = text.find(title)
                snippet = text[idx:idx+300] if idx != -1 else ""
                price_match = re.search(r'[\d,]+\s*円', snippet)
                price = price_match.group(0).strip() if price_match else "要確認"

                if any(kw in snippet for kw in CLOSED_KEYWORDS):
                    continue

                desc = re.sub(r'\s+', ' ', snippet.replace(title, "")).strip()[:150]

                jobs_raw.append({
                    "title": title,
                    "description": desc,
                    "price": price,
                    "link": href,
                })

        except Exception as e:
            print(f"[Scraper ERROR] {keyword} page={page}: {e}")
            break

    return jobs_raw


import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_scraping():
    global _jobs_data, _is_loading, _last_updated, _scrape_log
    _scrape_log.clear()
    _scrape_log.append("開始")
    print("[Scraper] スクレイピング開始（並列）...", flush=True)
    result = {cat_key: [] for cat_key in CATEGORIES}
    seen_links = set()
    lock = threading.Lock()

    # タスク一覧: (cat_key, keyword)
    tasks = [
        (cat_key, kw)
        for cat_key, cat_data in CATEGORIES.items()
        for kw in cat_data["search_keywords"]
    ]

    def fetch_task(cat_key, keyword):
        try:
            raw_jobs = scrape_crowdworks(keyword)
            return cat_key, keyword, raw_jobs, None
        except Exception as e:
            return cat_key, keyword, [], str(e)

    executor = ThreadPoolExecutor(max_workers=8)
    try:
        futures = {executor.submit(fetch_task, cat_key, kw): (cat_key, kw) for cat_key, kw in tasks}
        for future in as_completed(futures, timeout=60):
            cat_key, keyword, raw_jobs, err = future.result()
            msg = f"'{keyword}' → {len(raw_jobs)}件" if not err else f"'{keyword}' ERROR: {err}"
            _scrape_log.append(msg)
            print(f"[Scraper] {msg}", flush=True)
            with lock:
                for job in raw_jobs:
                    if job["link"] in seen_links:
                        continue
                    seen_links.add(job["link"])

                    combined = (job["title"] + " " + job["description"]).lower()

                    # 除外キーワードチェック
                    if any(kw in combined for kw in EXCLUDE_KEYWORDS):
                        continue

                    score, sub, tip, reason = score_job(job["title"], job["description"], cat_key)

                    # ★4未満は表示しない
                    if score < MIN_SCORE:
                        continue

                    result[cat_key].append({
                        **job,
                        "score": score,
                        "subcategory": sub,
                        "tip": tip,
                        "star_reason": reason,
                        "category": cat_key,
                    })
    except Exception as e:
        _scrape_log.append(f"タイムアウト or エラー: {e}")
        print(f"[Scraper] タイムアウト or エラー: {e}", flush=True)
    finally:
        executor.shutdown(wait=False)  # ハングしたスレッドを待たずに終了
        for cat_key in result:
            result[cat_key].sort(key=lambda x: x["score"], reverse=True)
        _jobs_data = result
        _last_updated = datetime.now()
        total = sum(len(v) for v in result.values())
        _scrape_log.append(f"完了（取得件数: {total}件）")
        print(f"[Scraper] 完了 総件数: {total}件", flush=True)
        _is_loading = False

    # 1時間後に自動再スクレイピング
    def _auto_refresh():
        time.sleep(60 * 60)
        global _is_loading
        if not _is_loading:
            _is_loading = True
            run_scraping()
    threading.Thread(target=_auto_refresh, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.route("/api/jobs")
def api_jobs():
    return jsonify({
        "loading": _is_loading,
        "last_updated": _last_updated.isoformat() if _last_updated else None,
        "jobs": _jobs_data,
    })


@app.route("/api/refresh")
def api_refresh():
    global _is_loading
    if not _is_loading:
        _is_loading = True
        threading.Thread(target=run_scraping, daemon=True).start()
    return jsonify({"status": "refreshing"})


@app.route("/api/star-criteria")
def star_criteria():
    criteria = {}
    for cat_key, cat in CATEGORIES.items():
        criteria[cat_key] = {
            "name": cat["name"],
            "icon": cat["icon"],
            "subs": {
                sub_name: {"score": sub["score"], "reason": sub.get("star_reason", "")}
                for sub_name, sub in cat["subcategories"].items()
            }
        }
    return jsonify(criteria)


PROFILE = """
応募者プロフィール：
- 名前：阪下航哉（さかしたこうや）
- 本業として会社員をしながら副業でフリーランスをしている
- ランサーズで約1年間の実績あり（データ入力、テキスト入力、動画・画像編集、簡単なWeb開発など）
- クラウドワークスは最近登録したばかり
"""

@app.route("/api/generate-message")
def generate_message():
    link = request.args.get("link", "")
    if not link or "crowdworks.jp" not in link:
        return jsonify({"error": "invalid link"}), 400

    # 案件ページの全文を取得（requestsで軽量取得）
    job_text = ""
    try:
        import requests as req
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        r = req.get(link, headers=headers, timeout=15)
        r.encoding = "utf-8"
        # タグ除去
        text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        job_text = text[:4000]
    except Exception as e:
        return jsonify({"error": f"ページ取得失敗: {e}"}), 500

    # Geminiで応募文生成
    try:
        from google import genai
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        prompt = f"""以下の案件詳細と応募者プロフィールをもとに、クラウドワークスの応募メッセージを作成してください。

【案件詳細】
{job_text}

{PROFILE}

【作成ルール】
- 【応募方法】に質問が記載されている場合は、必ずその質問に答えること
- 質問がない場合は自己紹介と経験・意欲をアピールする文章にすること
- 丁寧でフレンドリーな口調（です・ます調）
- 300〜400文字程度
- クラウドワークスは最近登録したばかりであることは自然に触れる程度でよい
- ランサーズでの実績は具体的に触れる
- メッセージ本文のみ出力（説明・前置き不要）"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        message = response.text.strip()
        return jsonify({"message": message})
    except Exception as e:
        return jsonify({"error": f"AI生成失敗: {e}"}), 500


@app.route("/api/debug")
def api_debug():
    return jsonify({
        "loading": _is_loading,
        "last_updated": _last_updated.isoformat() if _last_updated else None,
        "counts": {k: len(v) for k, v in _jobs_data.items()},
        "scrape_log": _scrape_log[-20:],
    })

if __name__ == "__main__":
    app.run(debug=False, port=5001)
