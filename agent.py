import os
import requests

try:
    import google.generativeai as genai
except ImportError:
    os.system("pip install google-generativeai")
    import google.generativeai as genai

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SCOPUS_API_KEY = os.getenv("SCOPUS_API_KEY", "")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "Adaptive Leadership OR Strategic Management OR Business Administration")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"فشل إرسال الرسالة إلى تليجرام: {response.text}")

def fetch_papers(query):
    papers = []
    
    # 1. البحث عبر Scopus API (إذا توفر المفتاح)
    if SCOPUS_API_KEY:
        print("جاري البحث في مستوعب Scopus العالمي...")
        scopus_url = "https://api.elsevier.com/content/search/scopus"
        scopus_headers = {
            "X-ELS-APIKey": SCOPUS_API_KEY,
            "Accept": "application/json"
        }
        scopus_params = {"query": query, "count": 2}
        try:
            scopus_res = requests.get(scopus_url, headers=scopus_headers, params=scopus_params)
            if scopus_res.status_code == 200:
                entries = scopus_res.json().get('search-results', {}).get('entry', [])
                for item in entries:
                    title = item.get('dc:title', 'بدون عنوان')
                    abstract = item.get('dc:description', 'بحث محكم معتمد في قاعدة بيانات Scopus.')
                    link = ""
                    for link_item in item.get('link', []):
                        if link_item.get('@ref') == 'scopus':
                            link = link_item.get('@href')
                    papers.append({"title": title, "summary": abstract, "link": link or "https://www.scopus.com"})
        except Exception as e:
            print(f"خطأ في الاتصال بـ Scopus: {str(e)}")

    # 2. البحث عبر Semantic Scholar
    if len(papers) < 2:
        print("جاري البحث في Semantic Scholar...")
        ss_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        ss_params = {"query": query, "limit": 2, "fields": "title,abstract,paperId"}
        ss_res = requests.get(ss_url, params=ss_params)
        
        if ss_res.status_code == 200:
            for item in ss_res.json().get('data', []):
                title = item.get('title', 'بدون عنوان')
                abstract = item.get('abstract') or ""
                paper_id = item.get('paperId')
                link = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""
                if title and not any(p['title'] == title for p in papers):
                    papers.append({"title": title, "summary": abstract, "link": link})
                
    # 3. المصدر الاحتياطي الأخير Crossref
    if not papers:
        print("التحويل للمصدر الأكاديمي الاحتياطي Crossref...")
        cr_url = "https://api.crossref.org/works"
        cr_params = {"query": query, "rows": 2, "sort": "published", "order": "desc"}
        cr_res = requests.get(cr_url, params=cr_params)
        
        if cr_res.status_code == 200:
            items = cr_res.json().get('message', {}).get('items', [])
            for item in items:
                title_list = item.get('title', [])
                title = title_list[0] if title_list else "بدون عنوان"
                abstract = item.get('abstract', 'بحث علمي حديث في مجال الإدارة والأعمال.')
                link = item.get('URL', '')
                papers.append({"title": title, "summary": abstract, "link": link})

    return papers[:3]

def summarize_and_translate(title, text):
    genai.configure(api_key=GEMINI_API_KEY)
    content_to_analyze = text if len(text) > 30 else f"عنوان البحث: {title}"
    prompt = (
        "أنت مستشار أكاديمي خبير في إدارة الأعمال والقيادة التكيفية. قم بترجمة العنوان والملخص التالي إلى العربية الفصحى، "
        "وقدم تحليلاً مهنياً في 3 نقاط واضحة (المشكلة الإدارية
