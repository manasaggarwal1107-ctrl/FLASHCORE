import urllib.request, re

url = 'https://flashcore-psi.vercel.app'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
print("HTML length:", len(html))
scripts = re.findall(r'src="([^"]+\.js)"', html)
print("Scripts:", scripts)

for s in scripts:
    s_url = url + s if s.startswith('/') else url + '/' + s
    print("Fetching script:", s_url)
    req_s = urllib.request.Request(s_url, headers={'User-Agent': 'Mozilla/5.0'})
    content = urllib.request.urlopen(req_s, timeout=15).read().decode('utf-8')
    print(f"Loaded {s}, size: {len(content)}")
    
    # Check for apiBaseUrl or backend URL
    urls = re.findall(r'https://[^"\'\s]+\.onrender\.com[^"\'\s]*', content)
    print("Found onrender URLs:", set(urls))
    
    # Check for /api
    if '/api' in content:
        print("Contains /api reference")
