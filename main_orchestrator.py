import os
import json
import time
import re
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------------------------------------
# 설정 파일 로드
# ---------------------------------------------------------
def load_config():
    with open("sync_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------
# 한터차트 (Physical) 크롤러 (Selenium 렌더링 방식)
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n" + "="*50)
    print(f"[Hanteo] 피지컬 일간 차트 수집 시작...")
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
        # 이미지 로딩 오프 (메모리 절약)
        prefs = {"profile.managed_default_content_settings.images": 2}
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.set_window_size(1920, 1080)
        wait = WebDriverWait(driver, 15)
        
        # 🌟 Buzz님이 알려주신 정확한 신규 한터차트 일간 주소 적용!
        driver.get("https://www.hanteochart.com/ko/charts/album/daily")
        
        # 차트 리스트 렌더링 대기
        time.sleep(5) # React 사이트 렌더링 넉넉히 대기
        
        # 100위까지 렌더링하기 위해 스크롤 다운
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 신규 사이트 구조에 맞춘 광범위 CSS 셀렉터
        items = soup.select('div[class*="list-item"], li[class*="item"], div[class*="row"], div[class*="AlbumChart"]')
        
        # CSS로 명확히 못 찾은 경우 텍스트 기반으로 앨범 블록 역추적 (딥러닝 탐색)
        if not items or len(items) < 10:
            print("  기본 구조 탐색 실패, 숫자 태그 기반 딥러닝 탐색 중...")
            rank_tags = soup.find_all(string=re.compile(r'^\d{1,3}$'))
            valid_items = []
            for tag in rank_tags:
                parent = tag.find_parent('div') or tag.find_parent('li')
                if parent and parent not in valid_items:
                    valid_items.append(parent)
            items = valid_items
            
        items = items[:limit]
        
        for idx, item in enumerate(items, 1):
            text_blocks = [t.strip() for t in item.get_text(separator='|').split('|') if t.strip()]
            clean_texts = [t for t in text_blocks if not t.isdigit() and t not in ['-', 'NEW', 'UP', 'DOWN'] and not t.startswith('0')]
            
            album_name = clean_texts[0] if len(clean_texts) > 0 else "정보 없음"
            artist_name = clean_texts[1] if len(clean_texts) > 1 else "정보 없음"
            
            # 판매량(지수) 찾기: 쉼표가 들어간 숫자 추출
            sales = "0"
            numbers = [t for t in text_blocks if ',' in t and any(c.isdigit() for c in t)]
            if numbers:
                sales = numbers[0] 
                
            if album_name == "정보 없음":
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
        print(f"[Hanteo] 에러 발생: {e}")
    finally:
        if driver: driver.quit()
        
    return pd.DataFrame(hanteo_data)

# ---------------------------------------------------------
# 디지털 차트 통합 크롤러 (스켈레톤)
# ---------------------------------------------------------
def scrape_digital_charts(jobs):
    print("\n[Digital] 차트 수집기는 다음 페이즈에 병합됩니다.")
    pass

# ---------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------
def main():
    print("NIKE (New Insights for K-pop Explorers) 오케스트레이터 가동\n")
    config = load_config()
    
    physical_df = pd.DataFrame()
    
    for job in config.get("jobs", []):
        if not job.get("enabled", False):
            continue
            
        if job["service"] == "hanteo":
            physical_df = scrape_hanteo_daily(limit=job.get("entity_limit", 100))
        
        elif job["hype_group"] == "digital":
            pass
            
    # 수집 결과 요약 및 CSV 저장
    if not physical_df.empty:
        print(f"\n✅ 한터차트 수집 완료: 총 {len(physical_df)} 건")
        # CSV 저장 (Artifacts 업로드용)
        physical_df.to_csv("hanteo_test_result.csv", index=False, encoding="utf-8-sig")
        print("결과가 hanteo_test_result.csv 로 안전하게 저장되었습니다.")
    else:
        print("\n❌ 한터차트 데이터가 수집되지 않았습니다.")

if __name__ == "__main__":
    main()
