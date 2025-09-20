from playwright.sync_api import sync_playwright

# 1. 설정
SEARCH_KEYWORD = "playwright 동시성 문제"
OUTPUT_FILE = "tests/fixtures/naver_blog_search_less_than_10.html"

# 2. Playwright 실행
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    # 네이버 검색
    url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query={SEARCH_KEYWORD}"
    page.goto(url, wait_until="networkidle")
    
    # HTML 저장
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(page.content())
    
    browser.close()
    print(f"성공적으로 '{OUTPUT_FILE}'에 저장했습니다.")
