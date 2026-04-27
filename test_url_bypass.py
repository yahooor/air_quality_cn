"""Test which URL format bypasses 403 on air-quality.com"""
import urllib.request
import ssl
import socket

socket.setdefaulttimeout(15)
ctx = ssl.create_default_context()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

URLS = [
    'https://air-quality.com/summary/china/beijing/haidian-district',
    'https://air-quality.com/summary/china/beijing/haidian-district?lang=zh',
    'https://www.air-quality.com/summary/china/beijing/haidian-district',
    'https://www.air-quality.com/summary/china/beijing/haidian-district?lang=zh',
    'https://air-quality.com/summary/city/china/beijing?lang=zh',
    'https://air-quality.com/entry/china/beijing?lang=zh',
]

for url in URLS:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        r = urllib.request.urlopen(req, context=ctx)
        text = r.read().decode('utf-8', errors='ignore')
        has_gauge = 'Gauge({' in text
        print(f'OK  {url} -> {r.status} len={len(text)} gauge={has_gauge}')
        if has_gauge:
            # Show gauge snippet
            idx = text.find('Gauge({')
            print(f'    GAUGE SNIPPET: {text[idx:idx+80]}')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        print(f'ERR {url} -> {e.code} {e.reason} body_len={len(body)}')
        print(f'    BODY PREVIEW: {body[:200]}')
    except Exception as e:
        print(f'ERR {url} -> {type(e).__name__}: {e}')
