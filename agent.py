import os
import requests

# إعدادات الحسابات والبحث (تم جعل مصطلح البحث أقصر وأكثر مرونة لجلب نتائج مضمونة)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "Adaptive Leadership")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("تم إرسال الرسالة إلى تليجرام بنجاح!")
    else:
        print(f"فشل إرسال الرسالة إلى تليجرام: {response.text}")

def fetch_semantic_scholar_papers(query):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=2&fields=title,abstract,paperId"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"خطأ في الاتصال بـ Semantic Scholar API: {response.text}")
        return []
    
    data = response.json()
    papers = []
    
    for item in data.get('data', []):
        title = item.get('title', 'بدون عنوان')
        abstract = item.get('abstract') or "لا يوجد ملخص متاح لهذا البحث."
        paper_id = item.get('paperId')
        link = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else "https://www.semanticscholar.org"
        
        papers.append({"title": title, "summary": abstract, "link": link})
    
    return papers

def summarize_and_translate(text):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    prompt = "قم بترجمة هذا الملخص العلمي الإداري إلى اللغة العربية الفصحى بأسلوب مهني واحترافي، وقم بتلخيصه في 3 نقاط رئيسية واضحة (التحدي الإداري، المنهجية، الآثار القيادية):\n\n" + text
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        try:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"خطأ في تحليل استجابة الذكاء الاصطناعي: {str(e)}"
    else:
        return f"خطأ في الاتصال بـ Gemini API: {response.text}"

if __name__ == "__main__":
    print("بدء عمل وكيل أبحاث القيادة التكيفية...")
    papers = fetch_semantic_scholar_papers(SEARCH_QUERY)
    
    if not papers:
        print("لم يتم العثور على مقالات، سيتم إرسال تنبيه.")
        send_telegram_message("⚠️ بدأ الوكيل العمل ولكن لم يتم العثور على أبحاث جديدة مطابقة لهذا البحث اليوم.")
    else:
        for paper in papers:
            print(f"معالجة بحث: {paper['title']}")
            ai_output = summarize_and_translate(paper['summary'])
            
            message = (
                "📊 بحث جديد في القيادة التكيفية والإدارة\n\n"
                f"🔗 العنوان: {paper['title']}\n"
                f"🌐 الرابط: {paper['link']}\n\n"
                f"🤖 التحليل الإداري والترجمة:\n{ai_output}\n\n"
                "-----------------------------------"
            )
            
            send_telegram_message(message)
            
    print("تم الانتهاء من تنفيذ الوكيل بالكامل!")
