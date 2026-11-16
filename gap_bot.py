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
# استعلام مخصص للتركيز على الأبحاث الحديثة والقيود والتوجهات المستقبلية في الإدارة والقيادة
GAP_QUERY = os.getenv("GAP_QUERY", "Adaptive Leadership future research OR Strategic Management limitations")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"فشل إرسال الرسالة إلى تليجرام: {response.text}")

def fetch_recent_papers(query):
    papers = []
    
    # 1. البحث عبر Scopus API (إذا توفر المفتاح)
    if SCOPUS_API_KEY:
        print("جاري البحث في Scopus لاستخراج الفجوات...")
        scopus_url = "https://api.elsevier.com/content/search/scopus"
        scopus_headers = {
            "X-ELS-APIKey": SCOPUS_API_KEY,
            "Accept": "application/json"
        }
        scopus_params = {"query": query, "count": 2, "sort": "coverDate"}
        try:
            scopus_res = requests.get(scopus_url, headers=scopus_headers, params=scopus_params)
            if scopus_res.status_code == 200:
                entries = scopus_res.json().get('search-results', {}).get('entry', [])
                for item in entries:
                    title = item.get('dc:title', 'بدون عنوان')
                    abstract = item.get('dc:description', '')
                    link = ""
                    for link_item in item.get('link', []):
                        if link_item.get('@ref') == 'scopus':
                            link = link_item.get('@href')
                    if abstract:
                        papers.append({"title": title, "summary": abstract, "link": link or "https://www.scopus.com"})
        except Exception as e:
            print(f"خطأ في الاتصال بـ Scopus: {str(e)}")

    # 2. البحث عبر Semantic Scholar (يركز على الأوراق التي تحتوي على ملخصات غنية)
    if len(papers) < 2:
        print("جاري البحث في Semantic Scholar...")
        ss_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        ss_params = {
            "query": "Adaptive Leadership Business Administration",
            "limit": 5,
            "fields": "title,abstract,paperId,year"
        }
        ss_res = requests.get(ss_url, params=ss_params)
        
        if ss_res.status_code == 200:
            for item in ss_res.json().get('data', []):
                title = item.get('title', 'بدون عنوان')
                abstract = item.get('abstract') or ""
                paper_id = item.get('paperId')
                link = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else ""
                # نختار الأبحاث التي تحتوي على ملخص كافٍ لاستخراج الفجوة منه
                if len(abstract) > 100 and not any(p['title'] == title for p in papers):
                    papers.append({"title": title, "summary": abstract, "link": link})
                    if len(papers) >= 2:
                        break
                
    # 3. المصدر الاحتياطي Crossref
    if not papers:
        print("التحويل للمصدر الاحتياطي Crossref...")
        cr_url = "https://api.crossref.org/works"
        cr_params = {"query": "Adaptive Leadership", "rows": 2, "sort": "published", "order": "desc"}
        cr_res = requests.get(cr_url, params=cr_params)
        
        if cr_res.status_code == 200:
            items = cr_res.json().get('message', {}).get('items', [])
            for item in items:
                title_list = item.get('title', [])
                title = title_list[0] if title_list else "بدون عنوان"
                abstract = item.get('abstract', 'دراسة حديثة في القيادة التكيفية وإدارة الأعمال.')
                link = item.get('URL', '')
                papers.append({"title": title, "summary": abstract, "link": link})

    return papers[:2]

def discover_research_gaps(title, text):
    genai.configure(api_key=GEMINI_API_KEY)
    content_to_analyze = text if len(text) > 30 else f"عنوان البحث: {title}"
    
    prompt = f"""أنت بروفيسور ومشرف أكاديمي متخصص في مناهج البحث العلمي وإدارة الأعمال والقيادة التكيفية. 
حلل الدراسة التالية بدقة واستخرج منها الفرص البحثية لطلاب الماجستير والدكتوراه باللغة العربية الفصحى وفق الهيكل التالي:

1. ترجمة العنوان وفكرة الدراسة باختصار شديد (سطرين).
2. القصور أو القيود البحثية المحتملة (Limitations): ما الذي لم تغطه هذه الدراسة؟ (مثل: البيئة الجغرافية، القطاع، حجم العينة، أو المتغيرات الوسيطة).
3. الفجوة البحثية المستنبطة (Research Gap): ما هي المنطقة المعرفية غير المستكشفة التي تفتحها هذه الدراسة؟
4. عنوان مقترح لرسالة ماجستير أو دكتوراه مبني على هذه الفجوة (مع تحديد المتغير المستقل والتابع).

بيانات الدراسة:
العنوان: {title}
الملخص: {content_to_analyze}"""
    
    supported_models = ['gemini-3.8-flash', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    
    for model_name in supported_models:
        try:
            print(f"تحليل الفجوات باستخدام النموذج: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"فشل النموذج {model_name}: {str(e)}")
            continue
            
    return "⚠️ تعذر استخراج الفجوات البحثية حالياً."

if __name__ == "__main__":
    print("بدء تشغيل وكيل اكتشاف الفجوات البحثية...")
    papers = fetch_recent_papers(GAP_QUERY)
    
    if not papers:
        send_telegram_message("⚠️ لم يتم العثور على أبحاث كافية لتحليل الفجوات اليوم.")
    else:
        for paper in papers:
            print(f"استخراج الفجوات من: {paper['title']}")
            gap_analysis = discover_research_gaps(paper['title'], paper['summary'])
            message = (
                "🔍 تقرير اكتشاف الفجوات البحثية\n\n"
                f"📄 الدراسة المرجعية: {paper['title']}\n"
                f"🌐 الرابط: {paper['link']}\n\n"
                f"💡 تحليل الفجوات والمقترحات:\n{gap_analysis}\n"
                "==================================="
            )
            send_telegram_message(message)
    print("تم إرسال تقرير الفجوات بنجاح.")
