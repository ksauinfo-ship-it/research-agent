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
GAP_QUERY = os.getenv("GAP_QUERY", "Adaptive Leadership OR Strategic Management")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    # تقسيم الرسالة تلقائياً إذا تجاوزت الحد الأقصى المسموح في تليجرام (4000 حرف)
    max_length = 3800
    chunks = [message[i:i + max_length] for i in range(0, len(message), max_length)]
    
    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk
        }
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code != 200:
                print(f"فشل إرسال الرسالة إلى تليجرام: {response.text}", flush=True)
            else:
                print("تم تسليم الرسالة إلى تليجرام بنجاح!", flush=True)
        except Exception as e:
            print(f"خطأ في الاتصال بتليجرام: {str(e)}", flush=True)

def fetch_recent_papers(query):
    papers = []
    
    # 1. البحث عبر Scopus API
    if SCOPUS_API_KEY:
        print("جاري البحث في Scopus لاستخراج الفجوات...", flush=True)
        scopus_url = "https://api.elsevier.com/content/search/scopus"
        scopus_headers = {
            "X-ELS-APIKey": SCOPUS_API_KEY,
            "Accept": "application/json"
        }
        scopus_params = {"query": query, "count": 2}
        try:
            scopus_res = requests.get(scopus_url, headers=scopus_headers, params=scopus_params, timeout=15)
            if scopus_res.status_code == 200:
                entries = scopus_res.json().get('search-results', {}).get('entry', [])
                for item in entries:
                    title = item.get('dc:title', 'بدون عنوان')
                    abstract = item.get('dc:description', 'دراسة حديثة في مجال الإدارة والقيادة التكيفية.')
                    link = ""
                    for link_item in item.get('link', []):
                        if link_item.get('@ref') == 'scopus':
                            link = link_item.get('@href')
                    papers.append({"title": title, "summary": abstract, "link": link or "https://www.scopus.com"})
        except Exception as e:
            print(f"تجاوز Scopus: {str(e)}", flush=True)

    # 2. البحث عبر Semantic Scholar
    if len(papers) < 2:
        print("جاري البحث في Semantic Scholar...", flush=True)
        ss_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        ss_params = {
            "query": "Adaptive Leadership Business Administration",
            "limit": 4,
            "fields": "title,abstract,paperId"
        }
        try:
            ss_res = requests.get(ss_url, params=ss_params, timeout=15)
            if ss_res.status_code == 200:
                for item in ss_res.json().get('data', []):
                    title = item.get('title', 'بدون عنوان')
                    abstract = item.get('abstract') or ""
                    paper_id = item.get('paperId')
                    link = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""
                    if len(abstract) > 50 and not any(p['title'] == title for p in papers):
                        papers.append({"title": title, "summary": abstract, "link": link})
                        if len(papers) >= 2:
                            break
        except Exception as e:
            print(f"تجاوز Semantic Scholar: {str(e)}", flush=True)
                
    # 3. المصدر الاحتياطي Crossref
    if not papers:
        print("التحويل للمصدر الاحتياطي Crossref...", flush=True)
        cr_url = "https://api.crossref.org/works"
        cr_params = {"query": "Adaptive Leadership", "rows": 2, "sort": "published", "order": "desc"}
        try:
            cr_res = requests.get(cr_url, params=cr_params, timeout=15)
            if cr_res.status_code == 200:
                items = cr_res.json().get('message', {}).get('items', [])
                for item in items:
                    title_list = item.get('title', [])
                    title = title_list[0] if title_list else "بدون عنوان"
                    abstract = item.get('abstract', 'دراسة حديثة في القيادة التكيفية وإدارة الأعمال.')
                    link = item.get('URL', '')
                    papers.append({"title": title, "summary": abstract, "link": link})
        except Exception as e:
            print(f"خطأ في Crossref: {str(e)}", flush=True)

    return papers[:2]

def discover_research_gaps(title, text):
    genai.configure(api_key=GEMINI_API_KEY)
    content_to_analyze = text if len(text) > 30 else f"عنوان البحث: {title}"
    
    prompt = f"""أنت بروفيسور ومشرف أكاديمي متخصص في مناهج البحث العلمي وإدارة الأعمال والقيادة التكيفية. 
حلل الدراسة التالية باختصار وتركيز عالٍ (بما لا يتجاوز 250 كلمة) واستخرج منها الفرص البحثية باللغة العربية الفصحى وفق الهيكل التالي بدون أي رموز تنسيق معقدة:

1. فكرة الدراسة باختصار (سطرين).
2. القصور أو القيود البحثية المحتملة (Limitations): ما الذي لم تغطه الدراسة؟
3. الفجوة البحثية المستنبطة (Research Gap): المنطقة المعرفية غير المستكشفة.
4. عنوان مقترح لرسالة ماجستير أو دكتوراه (مع تحديد المتغير المستقل والتابع).

بيانات الدراسة:
العنوان: {title}
الملخص: {content_to_analyze}"""
    
    preferred_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower():
                preferred_models.append(m.name)
    except Exception as e:
        print(f"تنبيه جلب النماذج: {str(e)}", flush=True)

    for fb in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-pro']:
        if fb not in preferred_models:
            preferred_models.append(fb)
    
    for model_name in preferred_models[:4]:
        try:
            print(f"تحليل الفجوات باستخدام النموذج: {model_name}", flush=True)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"تجاوز {model_name}: {str(e)}", flush=True)
            continue
            
    return "⚠️ تعذر استخراج الفجوات البحثية حالياً."

if __name__ == "__main__":
    print("بدء تشغيل وكيل اكتشاف الفجوات البحثية...", flush=True)
    papers = fetch_recent_papers(GAP_QUERY)
    
    if not papers:
        send_telegram_message("⚠️ لم يتم العثور على أبحاث كافية لتحليل الفجوات اليوم.")
    else:
        for paper in papers:
            print(f"استخراج الفجوات من: {paper['title']}", flush=True)
            gap_analysis = discover_research_gaps(paper['title'], paper['summary'])
            message = (
                "🔍 تقرير اكتشاف الفجوات البحثية\n\n"
                f"📄 الدراسة المرجعية: {paper['title']}\n"
                f"🌐 الرابط: {paper['link']}\n\n"
                f"💡 تحليل الفجوات والمقترحات:\n{gap_analysis}\n"
                "==================================="
            )
            send_telegram_message(message)
    print("تمت العملية بالكامل.", flush=True)
