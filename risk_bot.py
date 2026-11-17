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

# حصر البحث في تخصص إدارة الأعمال (BUSI) داخل سكوبس
RISK_QUERY = os.getenv(
    "RISK_QUERY",
    '("Risk Management Behavior" OR "Risk-Taking Behavior" OR "Risk Behavior") AND ("Business Administration" OR "Organizational" OR "Corporate" OR "Enterprise") AND SUBJAREA(BUSI)'
)

def clean_html(raw_html):
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

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

def fetch_risk_papers(query):
    papers = []
    
    # 1. البحث عبر Scopus API (محصور في تخصص إدارة الأعمال BUSI)
    if SCOPUS_API_KEY:
        print("جاري البحث في Scopus (تخصص إدارة الأعمال) عن سلوك إدارة المخاطر...", flush=True)
        scopus_url = "https://api.elsevier.com/content/search/scopus"
        scopus_headers = {
            "X-ELS-APIKey": SCOPUS_API_KEY,
            "Accept": "application/json"
        }
        scopus_params = {"query": query, "count": 2, "sort": "coverDate"}
        try:
            scopus_res = requests.get(scopus_url, headers=scopus_headers, params=scopus_params, timeout=15)
            if scopus_res.status_code == 200:
                entries = scopus_res.json().get('search-results', {}).get('entry', [])
                for item in entries:
                    title = item.get('dc:title', 'بدون عنوان')
                    abstract = item.get('dc:description', '')
                    journal = item.get('prism:publicationName', 'غير محدد في السجل')
                    pub_date = item.get('prism:coverDate', 'غير محدد')
                    author = item.get('dc:creator', 'غير محدد')
                    doi = item.get('prism:doi', 'لا يوجد')
                    
                    affiliations = item.get('affiliation', [])
                    country = "غير محدد"
                    inst = "غير محدد"
                    if isinstance(affiliations, list) and affiliations:
                        country = affiliations[0].get('affiliation-country', 'غير محدد')
                        inst = affiliations[0].get('affilname', 'غير محدد')
                    elif isinstance(affiliations, dict):
                        country = affiliations.get('affiliation-country', 'غير محدد')
                        inst = affiliations.get('affilname', 'غير محدد')
                        
                    link = f"https://doi.org/{doi}" if doi != 'لا يوجد' else "https://www.scopus.com"
                    
                    papers.append({
                        "title": title,
                        "abstract": abstract or "لم يتوفر نص المستخلص الكامل في واجهة العرض السريع.",
                        "journal": journal,
                        "date": pub_date,
                        "author": author,
                        "country": f"{country} ({inst})",
                        "doi": doi,
                        "link": link
                    })
        except Exception as e:
            print(f"تجاوز Scopus: {str(e)}", flush=True)

    # 2. البحث عبر Semantic Scholar مع تقييد النطاق بإدارة الأعمال
    if len(papers) < 2:
        print("جاري البحث في Semantic Scholar (إدارة الأعمال)...", flush=True)
        ss_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        ss_params = {
            "query": "Risk Management Behavior Business Administration Corporate",
            "fieldsOfStudy": "Business",
            "limit": 4,
            "fields": "title,abstract,venue,year,publicationDate,authors,externalIds,paperId"
        }
        try:
            ss_res = requests.get(ss_url, params=ss_params, timeout=15)
            if ss_res.status_code == 200:
                for item in ss_res.json().get('data', []):
                    title = item.get('title', 'بدون عنوان')
                    abstract = item.get('abstract') or ""
                    if len(abstract) > 50 and not any(p['title'] == title for p in papers):
                        authors_list = [a.get('name') for a in item.get('authors', [])[:3]]
                        author = ", ".join(authors_list) if authors_list else "غير محدد"
                        journal = item.get('venue') or "مجلة علمية محكمة في إدارة الأعمال"
                        pub_date = item.get('publicationDate') or str(item.get('year', 'غير محدد'))
                        doi = item.get('externalIds', {}).get('DOI', 'لا يوجد')
                        paper_id = item.get('paperId')
                        link = f"https://doi.org/{doi}" if doi != 'لا يوجد' else f"https://www.semanticscholar.org/paper/{paper_id}"
                        
                        papers.append({
                            "title": title,
                            "abstract": abstract,
                            "journal": journal,
                            "date": pub_date,
                            "author": author,
                            "country": "يُستنتج من بيانات المؤلفين/المجلة",
                            "doi": doi,
                            "link": link
                        })
                        if len(papers) >= 2:
                            break
        except Exception as e:
            print(f"تجاوز Semantic Scholar: {str(e)}", flush=True)

    # 3. المصدر الاحتياطي Crossref مع تركيز إدارة الأعمال
    if not papers:
        print("التحويل للمصدر الاحتياطي Crossref (إدارة الأعمال)...", flush=True)
        cr_url = "https://api.crossref.org/works"
        cr_params = {
            "query": "Risk Management Behavior Business Administration Corporate",
            "rows": 2,
            "sort": "published",
            "order": "desc"
        }
        try:
            cr_res = requests.get(cr_url, params=cr_params, timeout=15)
            if cr_res.status_code == 200:
                items = cr_res.json().get('message', {}).get('items', [])
                for item in items:
                    title_list = item.get('title', [])
                    title = title_list[0] if title_list else "بدون عنوان"
                    abstract = clean_html(item.get('abstract', '')) or "دراسة حديثة حول سلوك إدارة المخاطر في إدارة الأعمال."
                    journal_list = item.get('container-title', [])
                    journal = journal_list[0] if journal_list else "غير محدد"
                    date_parts = item.get('published', {}).get('date-parts', [[None]])[0]
                    pub_date = "-".join(str(x) for x in date_parts if x) or "غير محدد"
                    authors_raw = item.get('author', [])
                    author = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors_raw[:3]]) or "غير محدد"
                    doi = item.get('DOI', 'لا يوجد')
                    link = item.get('URL', '')
                    
                    papers.append({
                        "title": title,
                        "abstract": abstract,
                        "journal": journal,
                        "date": pub_date,
                        "author": author,
                        "country": "غير محدد في سجل Crossref",
                        "doi": doi,
                        "link": link
                    })
        except Exception as e:
            print(f"خطأ في Crossref: {str(e)}", flush=True)

    return papers[:2]

def translate_and_format_details(paper):
    genai.configure(api_key=GEMINI_API_KEY)
    
    prompt = f"""أنت مترجم وباحث أكاديمي متخصص في إدارة الأعمال وإدارة المخاطر المؤسسية.
لديك البيانات الوصفية التالية لدراسة علمية حول "سلوك إدارة المخاطر" في مجال إدارة الأعمال. 
المطلوب: ترجمة كافة البيانات بدقة واحترافية إلى اللغة العربية الفصحى، واستنتاج الدولة/بلد النشر أو الانتماء من اسم المجلة أو الجهة إن أمكن، وتقديمها في بطاقة تعريفية منظمة وواضحة بدون أي رموز تنسيق معقدة (مثل النجمتين) وفق القالب التالي تماماً:

1. العنوان المترجم:
2. العنوان الأصلي:
3. الباحثون:
4. المجلة الناشرة:
5. تاريخ النشر:
6. الدولة / الانتماء المؤسسي:
7. معرف الوثيقة (DOI):
8. ترجمة المستخلص (Abstract) بالكامل وبأسلوب أكاديمي رصين:
9. أبرز نتائج أو تطبيقات الدراسة في إدارة الأعمال وسلوك إدارة المخاطر (في سطرين):

البيانات الخام للدراسة:
- العنوان: {paper['title']}
- الباحثون: {paper['author']}
- المجلة: {paper['journal']}
- التاريخ: {paper['date']}
- الدولة/الجهة: {paper['country']}
- DOI: {paper['doi']}
- المستخلص: {paper['abstract']}"""

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
            print(f"ترجمة وتنسيق البيانات باستخدام: {model_name}", flush=True)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"تجاوز {model_name}: {str(e)}", flush=True)
            continue
            
    return "⚠️ تعذر ترجمة التفاصيل آلياً في الوقت الحالي."

if __name__ == "__main__":
    print("بدء تشغيل وكيل رصد سلوك إدارة المخاطر (إدارة الأعمال)...", flush=True)
    papers = fetch_risk_papers(RISK_QUERY)
    
    if not papers:
        send_telegram_message("⚠️ لم يتم العثور على دراسات جديدة حول سلوك إدارة المخاطر في إدارة الأعمال اليوم.")
    else:
        for paper in papers:
            print(f"معالجة دراسة: {paper['title']}", flush=True)
            formatted_report = translate_and_format_details(paper)
            message = (
                "🛡️ راصد دراسات سلوك إدارة المخاطر (إدارة الأعمال)\n\n"
                f"{formatted_report}\n\n"
                f"🔗 الرابط المباشر للدراسة:\n{paper['link']}\n"
                "==================================="
            )
            send_telegram_message(message)
    print("تم إرسال تقارير سلوك إدارة المخاطر بنجاح.", flush=True)
