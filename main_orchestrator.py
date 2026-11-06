# ---------------------------------------------------------
# 한터차트 (Physical) 크롤러 (정밀 타겟팅 방식)
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n" + "="*50)
    print(f"[Hanteo] 피지컬 일간 차트 정밀 수집 시작...")
    print("="*50)
    
    driver = None
    hanteo_data = []
    scrape_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        prefs = {"profile.managed_default_content_settings.images": 2}
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_window_size(1920, 1080)
        wait = WebDriverWait(driver, 15)
        
        driver.get("https://www.hanteochart.com/ko/charts/album/daily")
        
        # 최상위 차트 컨테이너가 뜰 때까지 확실히 대기 (보통 id가 __next 이거나 특정 div)
        time.sleep(6) 
        
        for _ in range(4):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
        
        # 🌟 BeautifulSoup을 버리고, Selenium의 XPath를 사용해 화면상에 '순위 숫자'가 적힌 영역 주변만 정밀 타겟팅
        # 한터차트는 보통 1~100위 앞단에 숫자를 표기하므로 이를 기준으로 역추적합니다.
        
        rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'list') or contains(@class, 'row') or contains(@class, 'item')][.//span[re:match(text(), '^[0-9]+$')] or .//div[re:match(text(), '^[0-9]+$')]]")
        
        # 만약 위 방식으로 안 잡히면, 가장 확실한 차트 바디 영역 전체를 긁어옵니다.
        if not rows or len(rows) < 10:
             # 보통 한터차트 앨범명은 특정 폰트나 굵기 처리되므로, h4 태그나 특정 클래스를 가진 부모를 찾습니다.
             rows = driver.find_elements(By.XPATH, "//*[self::h4 or contains(@class, 'title') or contains(@class, 'album')]/ancestor::div[contains(@class, 'list') or contains(@class, 'item') or contains(@class, 'row')][1]")

        # 그래도 못 찾았다면 최후의 수단: 텍스트 덩어리를 긁어서 파싱
        if not rows or len(rows) < 10:
             print("  [경고] DOM 구조 방어막 발견. 텍스트 추출 모드로 강제 전환합니다.")
             page_text = driver.find_element(By.TAG_NAME, "body").text
             lines = page_text.split('\n')
             
             rank_counter = 1
             i = 0
             while i < len(lines) and rank_counter <= limit:
                 line = lines[i].strip()
                 # '1', '2' 등 순위 숫자로 시작하는 라인을 찾음
                 if line == str(rank_counter):
                     # 순위 아래쪽으로 앨범명, 아티스트명, 지수가 순서대로 있다고 가정
                     try:
                         # 중간에 'NEW', '-', 등락 숫자 등이 끼어있을 수 있으므로 필터링
                         info_lines = []
                         for j in range(1, 10):
                             if i+j >= len(lines): break
                             txt = lines[i+j].strip()
                             if txt and txt not in ['NEW', '-', 'UP', 'DOWN'] and not txt.isdigit():
                                 info_lines.append(txt)
                             if len(info_lines) >= 3: # 앨범명, 아티스트, 지수 3개 확보 시 중단
                                 break
                         
                         album_name = info_lines[0] if len(info_lines) > 0 else "정보 없음"
                         artist_name = info_lines[1] if len(info_lines) > 1 else "정보 없음"
                         
                         # 지수는 보통 쉼표가 들어간 숫자
                         sales = "0"
                         for txt in info_lines:
                             if ',' in txt and any(c.isdigit() for c in txt):
                                 sales = txt
                                 break
                         
                         if album_name not in ["홈", "차트", "월드", "회사 소개"] and album_name != "정보 없음":
                             hanteo_data.append({
                                 'tab_type': 'physical', 'platform': 'hanteo', 'rank': rank_counter,
                                 'album': album_name, 'artist': artist_name, 'sales_index': sales, 'scrape_time': scrape_time
                             })
                             print(f"  [{rank_counter}/{limit}] {album_name[:15]}... - {artist_name} (지수: {sales})")
                             rank_counter += 1
                     except Exception as e:
                         pass
                 i += 1
             
             return pd.DataFrame(hanteo_data)

        # 정상적인 DOM 탐색의 경우
        unique_rows = []
        for r in rows:
            if r not in unique_rows: unique_rows.append(r)
            
        items = unique_rows[:limit]
        
        for idx, item in enumerate(items, 1):
            text_blocks = item.text.split('\n')
            clean_texts = [t.strip() for t in text_blocks if t.strip() and not t.strip().isdigit() and t.strip() not in ['-', 'NEW', 'UP', 'DOWN']]
            
            album_name = clean_texts[0] if len(clean_texts) > 0 else "정보 없음"
            artist_name = clean_texts[1] if len(clean_texts) > 1 else "정보 없음"
            
            sales = "0"
            for t in clean_texts:
                if ',' in t and any(c.isdigit() for c in t):
                    sales = t
                    break
                    
            if album_name in ["홈", "차트", "월드", "회사 소개"] or album_name == "정보 없음":
                continue
                
            hanteo_data.append({
                'tab_type': 'physical',
                'platform': 'hanteo',
                'rank': idx,
                'album': album_name,
                'artist': artist_name,
                'sales_index': sales,
                'scrape_time': scrape_time
            })
            print(f"  [{idx}/{limit}] {album_name[:15]}... - {artist_name} (지수: {sales})")
            
    except Exception as e:
        print(f"[Hanteo] 렌더링 에러 발생: {e}")
    finally:
        if driver: driver.quit()
        
    return pd.DataFrame(hanteo_data)
