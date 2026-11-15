import os
import requests
import xml.etree.ElementTree as ET

# جلب الإعدادات من متغيرات البيئة (GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "Artificial Intelligence")

def fetch_arxiv_papers(query):
    url = f"http://export.arxiv.org/api/query?search_query=all:{query}&max_results=3&sortBy=submittedDate&sortOrder=descending"
    response = requests.get(url)
    if response.status_code != 200:
        print("خطأ في الاتصال بموقع arXiv")
        return []
    
    root = ET.fromstring(response.content)
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}
    papers = []
    
    for entry in root.findall('atom:entry', namespace):
        title = entry.find('atom:title', namespace).text.strip().replace('\n', ' ')
        summary = entry.find('atom:summary', namespace).text.strip().replace('\n', ' ')
        link = entry.find('atom:id', namespace).text
        papers.append({"title": title, "summary": summary, "link": link})
    
    return papers

def summarize_and_translate(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"قم بترجمة هذا الملخص العلمي إلى اللغة العربية الفصحى وقم بتلخيصه في 3 نقاط رئيسية واضحة (المشكلة، المنهجية، النتائج):\n\n{text}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
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

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM
