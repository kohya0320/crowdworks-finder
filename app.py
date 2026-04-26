from flask import Flask, render_template, jsonify, request
import requests as http_requests
import re
import time
import os
from datetime import datetime

app = Flask(__name__)

# 結果格納
_jobs_data = {cat: [] for cat in ["data_entry", "writing", "sns", "research"]}
_is_loading = False
_last_updated = None
_scrape_log = []
CACHE_TTL = 30 * 60

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# カテゴリ定義 & 星付け条件
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORIES = {
    "data_entry": {
        "name": "データ入力",
        "icon": "🗂️",
        "description": "テキスト・Excelへの転記など繰り返し作業",
        "search_keywords": ["データ入力", "コピペ 作業"],
        "subcategories": {
            "テキスト→Excel/CSV変換": {
                "keywords": ["テキスト", "excel", "エクセル", "csv", "変換", "スプレッドシート"],
                "score": 5,
                "tip": "Pythonで完全自動化可能。最も狙い目。",
                "star_reason": "⭐⭐⭐⭐⭐：入力フォーマットが完全に固定。Pythonスクリプト1本で全自動。"
            },
            "コピー&ペースト系": {
                "keywords": ["コピペ", "コピー", "貼り付け", "転記"],
                "score": 5,
                "tip": "Seleniumで完全自動化可能。",
                "star_reason": "⭐⭐⭐⭐⭐：操作が単純な繰り返し。Seleniumで全自動。"
            },
            "画像→テキスト入力(OCR)": {
                "keywords": ["画像", "領収書", "請求書", "スキャン", "写真"],
                "score": 4,
                "tip": "OCR+自動入力で対応。精度確認が必要。",
                "star_reason": "⭐⭐⭐⭐：OCR精度が課題だが自動化の枠組みは作れる。"
            },
            "Webリサーチ→入力": {
                "keywords": ["リサーチ", "web", "サイト", "url", "調査"],
                "score": 3,
                "tip": "スクレイピングで収集→入力が可能。",
                "star_reason": "⭐⭐⭐：サイト構造によっては難しい。要確認。"
            },
            "フォーム入力": {
                "keywords": ["フォーム", "登録", "申請", "応募"],
                "score": 3,
                "tip": "Seleniumで自動化できるが認証が障壁になることも。",
                "star_reason": "⭐⭐⭐：認証・CAPTCHA次第で難易度が変わる。"
            },
        }
    },
    "writing": {
        "name": "記事・ライティング",
        "icon": "✍️",
        "description": "AIで生成・量産できる文章系タスク",
        "search_keywords": ["ライティング", "商品説明 文章", "記事作成"],
        "subcategories": {
            "商品説明文": {
                "keywords": ["商品説明", "商品紹介", "ec", "楽天", "amazon", "商品文"],
                "score": 5,
                "tip": "フォーマット固定でAI量産が最も向いている。",
                "star_reason": "⭐⭐⭐⭐⭐：商品名・スペック→説明文の変換はAIが最得意。"
            },
            "定型フォーマット記事": {
                "keywords": ["フォーマット", "テンプレ", "定型", "ひな形", "指定"],
                "score": 5,
                "tip": "構成が固定なのでAI+スクリプトで量産可能。",
                "star_reason": "⭐⭐⭐⭐⭐：構成が決まっているためAI生成→そのまま納品が可能。"
            },
            "レビュー・口コミ": {
                "keywords": ["レビュー", "口コミ", "感想", "評価文"],
                "score": 4,
                "tip": "AIで生成可能。ジャンルごとにテンプレ化。",
                "star_reason": "⭐⭐⭐⭐：ジャンルを固定すればAIで量産しやすい。"
            },
            "SEO記事": {
                "keywords": ["seo", "キーワード", "上位", "検索", "ブログ"],
                "score": 3,
                "tip": "AIで生成可能だが品質チェックが必要。",
                "star_reason": "⭐⭐⭐：AIで下書き生成→人による確認が現実的。"
            },
        }
    },
    "sns": {
        "name": "SNS運用",
        "icon": "📱",
        "description": "コメント・投稿など反復的なSNS作業",
        "search_keywords": ["SNS運用", "Instagram 投稿"],
        "subcategories": {
            "コメント回り": {
                "keywords": ["コメント", "コメント周り", "コメント回り", "返信"],
                "score": 5,
                "tip": "Selenium+AIで完全自動化可能。",
                "star_reason": "⭐⭐⭐⭐⭐：AIでコメント文生成→Seleniumで自動投稿。完全自動化可。"
            },
            "いいね・フォロー": {
                "keywords": ["いいね", "フォロー", "フォロワー"],
                "score": 5,
                "tip": "Seleniumで自動化可能。BAN対策は必要。",
                "star_reason": "⭐⭐⭐⭐⭐：操作が単純でSeleniumで完全自動化。BAN対策に乱数wait推奨。"
            },
            "投稿・ポスト作成": {
                "keywords": ["投稿", "ポスト", "発信", "運用", "コンテンツ"],
                "score": 4,
                "tip": "AIで文章生成→自動投稿APIで対応。",
                "star_reason": "⭐⭐⭐⭐：AI生成+各SNSの公式APIで自動投稿可能。"
            },
            "DM・メッセージ送信": {
                "keywords": ["dm", "ダイレクト", "メッセージ送信", "message"],
                "score": 4,
                "tip": "AI+自動送信スクリプトで対応可能。",
                "star_reason": "⭐⭐⭐⭐：テンプレ+パーソナライズでAI生成→Selenium送信。"
            },
        }
    },
    "research": {
        "name": "リサーチ・収集",
        "icon": "🔍",
        "description": "スクレイピングで自動化できる情報収集系",
        "search_keywords": ["リスト作成", "企業リスト"],
        "subcategories": {
            "URL・リスト収集": {
                "keywords": ["url", "リスト", "一覧", "リンク", "サイト一覧"],
                "score": 5,
                "tip": "スクレイピングで完全自動化。最も向いている。",
                "star_reason": "⭐⭐⭐⭐⭐：スクレイピングの基本作業。Pythonで数分で終わる。"
            },
            "企業・店舗情報収集": {
                "keywords": ["企業", "会社", "法人", "店舗", "事業者"],
                "score": 4,
                "tip": "Webスクレイピングで自動収集可能。",
                "star_reason": "⭐⭐⭐⭐：対象サイトが決まれば自動収集スクリプトで対応。"
            },
            "価格・在庫調査": {
                "keywords": ["価格", "値段", "在庫", "競合", "相場"],
                "score": 4,
                "tip": "定期実行スクリプトで自動化可能。",
                "star_reason": "⭐⭐⭐⭐：EC系サイトなら構造が一定でスクレイピングしやすい。"
            },
            "画像・素材収集": {
                "keywords": ["画像", "素材", "写真", "ダウンロード", "収集"],
                "score": 4,
                "tip": "自動ダウンロードスクリプトで対応。",
                "star_reason": "⭐⭐⭐⭐：URLがわかれば自動ダウンロード+リネームで完全自動。"
            },
        }
    }
}


INTERVIEW_KEYWORDS = ["面接", "面談", "zoom", "zoomにて", "オンライン面接", "ビデオ通話",
                      "google meet", "teams", "skype", "電話面談", "事前面談", "ヒアリング"]

CLOSED_KEYWORDS = ["受付終了", "募集終了", "応募終了", "締め切り済", "終了しました", "受付を終了"]

def score_job(title, description, category_key):
    text = (title + " " + description).lower()
    category = CATEGORIES[category_key]
    best_score = 3   # 検索でヒットした時点で最低⭐3
    best_sub = "その他"
    best_tip = "カテゴリに合致。詳細を確認して自動化できるか判断してください。"
    best_reason = "⭐⭐⭐：検索キーワードに合致。内容確認で自動化の可否を判断。"

    for sub_name, sub_data in category["subcategories"].items():
        matches = sum(1 for kw in sub_data["keywords"] if kw in text)
        if matches > 0 and sub_data["score"] > best_score:
            best_score = sub_data["score"]
            best_sub = sub_name
            best_tip = sub_data["tip"]
            best_reason = sub_data.get("star_reason", "")

    # 面接・Zoom必要かチェック
    needs_interview = any(kw in text for kw in INTERVIEW_KEYWORDS)

    return best_score, best_sub, best_tip, best_reason, needs_interview


def scrape_crowdworks(keyword):
    """Jina AI Reader経由でCrowdWorksをスクレイピング（JS対応）"""
    import urllib.parse
    cw_url = f"https://crowdworks.jp/public/jobs/search?job_type=fixed&order=new&search[keyword]={urllib.parse.quote(keyword)}"
    jina_url = f"https://r.jina.ai/{cw_url}"
    jobs_raw = []

    try:
        headers = {
            "Accept": "text/plain",
            "User-Agent": "Mozilla/5.0",
        }
        jina_key = os.environ.get("JINA_API_KEY", "")
        if jina_key:
            headers["Authorization"] = f"Bearer {jina_key}"
        res = http_requests.get(jina_url, headers=headers, timeout=(10, 25))
        res.encoding = "utf-8"
        text = res.text

        # マークダウン形式のリンク [タイトル](URL) から案件を抽出
        links = re.findall(
            r'\[([^\]]{5,})\]\(https://crowdworks\.jp/public/jobs/(\d+)[^\)]*\)',
            text
        )

        seen_ids = set()
        for title, job_id in links[:40]:
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title = title.strip()
            if not title or len(title) < 5:
                continue

            href = f"https://crowdworks.jp/public/jobs/{job_id}"

            # タイトル周辺のテキストから金額を探す
            idx = text.find(title)
            snippet = text[idx:idx+300] if idx != -1 else ""
            price_match = re.search(r'[\d,]+\s*円', snippet)
            price = price_match.group(0).strip() if price_match else "要確認"

            # 終了案件を除外
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
        print(f"[Scraper ERROR] {keyword}: {e}")

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
                    score, sub, tip, reason, needs_interview = score_job(job["title"], job["description"], cat_key)
                    result[cat_key].append({
                        **job,
                        "score": score,
                        "subcategory": sub,
                        "tip": tip,
                        "star_reason": reason,
                        "needs_interview": needs_interview,
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
