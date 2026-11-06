import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------------------------------------
# 설정 파일 로드
# ---------------------------------------------------------
def load_config():
    with open("sync_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------
# 가벼운 드라이버 생성기 (메모리 최적화)
# ---------------------------------------------------------
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# ---------------------------------------------------------
# 한터차트 (Physical) 크롤러
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n" + "="*50)
    print(f"[Hanteo] 피지컬(음반) 일간 차트 수집 시작...")
    print("="*50)
    
    driver = None
    hanteo_data = []
    scrape_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        driver = get_driver()
        wait = WebDriverWait(driver, 15)
        # 한터차트 실시간/일간 음반 차트 URL (React 기반 SPA)
        driver.get("https://www.hanteochart.com/networkalbum/real")
        
        # 차트 리스트 렌더링 대기
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.list-item, .album-list')))
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 🌟 주의: 한터차트의 실제 CSS 클래스는 사이트 개편 시 변동될 수 있으므로,
        # 가장 일반적인 리스트 구조를 타겟팅합니다.
        items = soup.select('.list-item, .list-row, li[class*="album"]')[:limit]
        
        for idx, item in enumerate(items, 1):
            album_name = "정보 없음"
            artist_name = "정보 없음"
            sales = "0"
            
            # 앨범명, 아티스트명, 판매량 태그 추출 (일반적인 패턴)
            title_el = item.select_one('.title, .album-name, h4')
            artist_el = item.select_one('.artist, .singer, p')
            sales_el = item.select_one('.sales, .count, .num')
            
            if title_el: album_name = title_el.text.strip()
            if artist_el: artist_name = artist_el.text.strip()
            if sales_el: sales = sales_el.text.strip()
                
            if not album_name or album_name == "정보 없음":
                continue
                
            hanteo_data.append({
                'tab_type': 'physical',
                'platform': 'hanteo',
                'rank': idx,
                'album': album_name,
                'artist': artist_name,
                'sales_index': sales, # 판매량/지수
                'scrape_time': scrape_time
            })
            print(f"  [{idx}/{limit}] {album_name[:15]}... - {artist_name}")
            
    except Exception as e:
        print(f"[Hanteo] 에러 발생: {e}")
    finally:
        if driver: driver.quit()
        
    return pd.DataFrame(hanteo_data)

# ---------------------------------------------------------
# 디지털 차트 통합 크롤러 (스켈레톤)
# ---------------------------------------------------------
def scrape_digital_charts(jobs):
    # 이 부분은 이전 멜론/플로/벅스/지니 하이브리드 코드가 병합될 공간입니다.
    # 추후 매칭 엔진과 함께 완성될 예정입니다.
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
            # 디지털 차트는 통합하여 수집 예정
            pass
            
    # 수집 결과 요약
    if not physical_df.empty:
        print(f"\n✅ 한터차트 수집 완료: 총 {len(physical_df)} 건")
        # 테스트를 위해 임시 CSV 저장
        physical_df.to_csv("hanteo_test_result.csv", index=False, encoding="utf-8-sig")
        print("결과가 hanteo_test_result.csv 로 저장되었습니다.")

if __name__ == "__main__":
    main()
