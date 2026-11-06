import os
import json
import time
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------
# 설정 파일 로드
# ---------------------------------------------------------
def load_config():
    with open("sync_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------
# 안정성이 검증된 가벼운 드라이버 생성
# ---------------------------------------------------------
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# ---------------------------------------------------------
# 1. 한터차트 크롤러 (이번 테스트에서는 건너뜀)
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n[Hanteo] 피지컬 차트 수집은 이번 디지털 테스트에서 생략됩니다.")
    return pd.DataFrame()

# ---------------------------------------------------------
# 2. 디지털 차트 통합 크롤러 (Melon, Apple, Spotify, YTMusic)
# ---------------------------------------------------------
def scrape_digital_charts(jobs):
    print("\n" + "="*50)
    print("[Digital] 음원 차트 멀티 수집 시작...")
    print("="*50)
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    scrape_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    all_digital_data = []

    for job in jobs:
        platform = job['service']
        limit = job.get('entity_limit', 100)
        url = job['source_urls'][0]
        hype_weight = job.get('hype_weight', 0)
        
        print(f"\n📡 [{platform}] 차트 수집 중... (가중치: {hype_weight})")
        
        try:
            # --- 2.1 멜론 일간 차트 (API 정공법 - Requests) ---
            if platform == 'melon':
                res = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # 멜론 1~50위, 51~100위 묶음 리스트 추출
                songs = soup.select('tbody tr.lst50, tbody tr.lst100')[:limit]
                for idx, song in enumerate(songs, 1):
                    title_el = song.select_one('div.ellipsis.rank01 span a')
                    artist_el = song.select_one('div.ellipsis.rank02 span a')
                    
                    title = title_el.text.strip() if title_el else "정보 없음"
                    artist = artist_el.text.strip() if artist_el else "정보 없음"
                    
                    all_digital_data.append({
                        'tab_type': 'digital', 'platform': platform, 'rank': idx,
                        'title': title, 'artist': artist, 'hype_weight': hype_weight,
                        'scrape_time': scrape_time
                    })
                    if idx <= 3: print(f"  [{idx}위] {title} - {artist}")
            
            # --- 2.2 애플뮤직 차트 (Selenium 렌더링) ---
            elif platform == 'apple':
                driver = None
                try:
                    driver = get_driver()
                    driver.get(url)
                    time.sleep(5)
                    # 스크롤 다운
                    for _ in range(5):
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(1.5)
                    
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    songs = soup.select('.songs-list-row')[:limit]
                    for idx, song in enumerate(songs, 1):
                        title_el = song.select_one('.songs-list-row__song-name')
                        artist_el = song.select_one('.songs-list-row__by-line')
                        
                        title = title_el.text.strip() if title_el else "정보 없음"
                        artist = artist_el.text.strip() if artist_el else "정보 없음"
                        
                        all_digital_data.append({
                            'tab_type': 'digital', 'platform': platform, 'rank': idx,
                            'title': title, 'artist': artist, 'hype_weight': hype_weight,
                            'scrape_time': scrape_time
                        })
                        if idx <= 3: print(f"  [{idx}위] {title} - {artist}")
                finally:
                    if driver: driver.quit()

            # --- 2.3 스포티파이 Top 50 (Selenium 렌더링) ---
            elif platform == 'spotify':
                driver = None
                try:
                    driver = get_driver()
                    driver.get(url)
                    time.sleep(6)
                    
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    songs = soup.select('div[data-testid="tracklist-row"]')[:limit]
                    for idx, song in enumerate(songs, 1):
                        title_el = song.select_one('div[dir="auto"].t_yrXoUO3lN5126BSIo4')
                        if not title_el:
                             title_el = song.select_one('div[data-testid="internal-track-link"]')
                        
                        # 스포티파이는 여러 아티스트가 묶여있음
                        artist_els = song.select('span[data-testid="internal-track-link"]')
                        if not artist_els:
                            artist_els = song.select('a[data-testid="internal-track-link"]')
                        
                        title = title_el.text.strip() if title_el else "정보 없음"
                        artist = ", ".join([a.text.strip() for a in artist_els]) if artist_els else "정보 없음"
                        
                        all_digital_data.append({
                            'tab_type': 'digital', 'platform': platform, 'rank': idx,
                            'title': title, 'artist': artist, 'hype_weight': hype_weight,
                            'scrape_time': scrape_time
                        })
                        if idx <= 3: print(f"  [{idx}위] {title} - {artist}")
                finally:
                    if driver: driver.quit()

            # --- 2.4 유튜브 뮤직 차트 (우회 파싱 보류) ---
            elif platform == 'ytmusic':
                print("  [YTMusic] 유튜브 차트는 Selenium 접근 시 차단 확률이 높아 이번 테스트에서는 기본 구조만 확인합니다.")
                pass
                
        except Exception as e:
            print(f"[{platform}] 수집 중 에러: {e}")

    return pd.DataFrame(all_digital_data)

# ---------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------
def main():
    print("NIKE (New Insights for K-pop Explorers) 오케스트레이터 가동\n")
    config = load_config()
    
    # 🌟 필터링 조건 완화: 'enabled'가 True이고, 서비스 이름이 'hanteo'가 아닌 모든 것을 디지털 차트로 간주합니다.
    digital_jobs = [job for job in config.get("jobs", []) if job.get("enabled", True) and job.get("service", "") != "hanteo"]
    
    if digital_jobs:
        digital_df = scrape_digital_charts(digital_jobs)
        if not digital_df.empty:
            print(f"\n✅ 디지털 차트 수집 완료: 총 {len(digital_df)} 건")
            # 파일명을 워크플로우와 정확히 맞춤
            digital_df.to_csv("digital_test_result.csv", index=False, encoding="utf-8-sig")
            print("결과가 digital_test_result.csv 로 안전하게 저장되었습니다.")
        else:
            print("\n❌ 디지털 데이터가 수집되지 않았습니다.")
    else:
        print("\n⚠️ 실행할 디지털 차트 작업이 sync_config.json 에 없습니다.")

if __name__ == "__main__":
    main()
