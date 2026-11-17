import os
import re
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

SEARCH_QUERY = os.getenv(
    "SEARCH_QUERY",
    'TITLE-ABS-KEY(("Adaptive Leadership" OR "Strategic Leadership" OR "Organizational Management") AND ("Business" OR "Management" OR "Enterprise" OR "Corporate")) AND SUBJAREA(BUSI)'
)

EXCLUDED_WORDS = ["bone", "cell", "clinical", "patient", "cancer", "medical", "hospital", "nursing", "tissue", "matrix", "surgery", "disease", "soil", "toxic"]
REQUIRED_ADMIN_WORDS = ["management", "leadership", "business", "organizational", "corporate", "enterprise", "strategic", "administration", "governance", "firm", "manager"]

def clean_html(raw_html):
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def is_admin_related(title, journal, abstract):
    combined = f"{title} {journal} {abstract}".lower()
    if any(bad in combined for bad in EXCLUDED_WORDS):
        return False
    return any(good in combined for good in REQUIRED_ADMIN_WORDS)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
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
                print("تم تسليم التقرير إلى تليجرام بنجاح!", flush=True)
        except Exception as e:
            print(f"خطأ في الاتصال بتليجرام: {str(e)}", flush=True)

def fetch_admin_papers(query):
    papers = []
    
    # 1. البحث عبر Scopus API (تخصص إدارة الأعمال BUSI)
    if SCOPUS_API_KEY:
        print("جاري البحث في Scopus (الإدارة والقيادة)...", flush=True)
        scopus_url = "https://api.elsevier.com/content/search/scopus"
        scopus_headers = {
            "X-ELS-APIKey": SCOPUS_API_KEY,
            "Accept": "application/json"
        }
        scopus_params = {"query": query, "count": 5, "sort": "coverDate"}
        try:
            scopus_res = requests.get(scopus_url, headers=scopus_headers, params=scopus_params, timeout=15)
            if scopus_res.status_code == 200:
                entries = scopus_res.json().get('search-results', {}).get('entry', [])
                for item in entries:
                    title = item.get('dc:title', 'بدون عنوان')
                    abstract = item.get('dc:description', '')
                    journal = item.get('prism:publicationName', '')
                    if not is_admin_related(title, journal, abstract):
                        continue
                    doi = item.get('prism:doi', '')
                    link = f"https://doi.org/{doi}" if doi else "https://www.scopus.com"
                    papers.append({
                        "title": title,
                        "summary": abstract or f"دراسة في الإدارة والقيادة بعنوان: {title}",
                        "link": link
                    })
                    if len(papers) >= 2:
                        break
        except Exception as e:
            print(f"تجاوز Scopus: {str(e)}", flush=True)

    # 2. البحث عبر Semantic Scholar (حقل Business)
    if len(papers) < 2:
        print("جاري البحث في Semantic Scholar (الإدارة والقيادة)...", flush=True)
        ss_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        ss_params = {
            "query": "Adaptive Leadership Strategic Management Organization",
            "fieldsOfStudy": "Business",
            "limit": 8,
            "fields": "title,abstract,venue,externalIds,paperId"
        }
        try:
            ss_res = requests.get(ss_url, params=ss_params, timeout=15)
            if ss_res.status_code == 200:
                for item in ss_res.json().get('data', []):
                    title = item.get('title', 'بدون عنوان')
                    abstract = item.get('abstract') or ""
                    journal = item.get('venue') or ""
                    if len(abstract) > 50 and is_admin_related(title, journal, abstract) and not any(p['title'] == title for p in papers):
                        doi = item.get('externalIds', {}).get('DOI', '')
                        paper_id = item.get('paperId')
                        link = f"https://doi.org/{doi}" if doi else f"https://www.semanticscholar.org/paper/{paper_id}"
                        papers.append({"title": title, "summary": abstract, "link": link})
                        if len(papers) >= 2:
                            break
        except Exception as e:
            print(f"تجاوز Semantic Scholar: {str(e)}", flush=True)

    # 3. المصدر الاحتياطي Crossref
    if len(papers) < 2:
        print("البحث في Crossref ضمن عناوين الإدارة والقيادة...", flush=True)
        cr_url = "https://api.crossref.org/works"
        cr_params = {
            "query.title": "adaptive leadership management organization",
            "rows": 8,
            "sort": "relevance"
        }
        try:
            cr_res = requests.get(cr_url, params=cr_params, timeout=15)
            if cr_res.status_code == 200:
                items = cr_res.json().get('message', {}).get('items', [])
                for item in items:
                    title_list = item.get('title', [])
                    title = title_list[0] if title_list else "بدون عنوان"
                    abstract = clean_html(item.get('abstract', ''))
                    journal_list = item.get('container-title', [])
                    journal = journal_list[0] if journal_list else ""
                    if not is_admin_related(title, journal, abstract) or any(p['title'] == title for p in papers):
                        continue
                    link = item.get('URL', '')
                    papers.append({
                        "title": title,
                        "summary": abstract or f"بحث محكم في الإدارة والقيادة بعنوان: {title}",
                        "link": link
                    })
                    if len(papers) >= 2:
                        break
        except Exception as e:
            print(f"خطأ في Crossref: {str(e)}", flush=True)

    return papers[:2]

def analyze_admin_paper(title, text):
    genai.configure(api_key=GEMINI_API_KEY)
    
    prompt = f"""أنت مستشار وباحث أكاديمي متخصص في الإدارة والقيادة التنظيمية.
أولاً: تحقق من عنوان الدراسة ومحتواها أدناه. إذا كانت الدراسة خارج مجال الإدارة أو القيادة أو إدارة الأعمال (مثل الطب أو البيولوجيا أو الهندسة)، أجب بكلمة واحدة فقط: SKIP

ثانياً: إذا كانت الدراسة في الإدارة والقيادة، فقدم تحليلاً إدارياً موجزاً وعملياً باللغة العربية الفصحى بدون رموز تنسيق معقدة (مثل النجمتين) وفق الهيكل التالي:
1. ترجمة العنوان وفكرة البحث الرئيسية (سطرين).
2. أهم النتائج الإدارية والقيادية.
3. التوصيات العملية للمديرين والقادة في بيئة الأعمال.

العنوان: {title}
المحتوى: {text}"""

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
            print(f"تحليل البحث باستخدام: {model_name}", flush=True)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"تجاوز {model_name}: {str(e)}", flush=True)
            continue
            
    return "⚠️ تعذر توليد التحليل باستخدام النماذج المتاحة حالياً."

if __name__ == "__main__":
    print("بدء تشغيل وكيل الرصد والتحليل في الإدارة والقيادة...", flush=True)
    papers = fetch_admin_papers(SEARCH_QUERY)
    
    sent_count = 0
    for paper in papers:
        print(f"معالجة بحث: {paper['title']}", flush=True)
        analysis = analyze_admin_paper(paper['title'], paper['summary'])
        if analysis == "SKIP":
            print(f"تم استبعاد البحث لأنه خارج تخصص الإدارة: {paper['title']}", flush=True)
            continue
            
        message = (
            "📚 بحث محكم في الإدارة والقيادة\n\n"
            f"🔗 العنوان: {paper['title']}\n"
            f"🌐 الرابط: {paper['link']}\n\n"
            f"🤖 التحليل الإداري:\n{analysis}\n"
            "==================================="
        )
        send_telegram_message(message)
        sent_count += 1
        
    if sent_count == 0:
        send_telegram_message("⚠️ لم يتم العثور على أبحاث مطابقة لتخصص الإدارة والقيادة اليوم.")
    print("اكتملت مهمة الوكيل الأول بنجاح.", flush=True)
