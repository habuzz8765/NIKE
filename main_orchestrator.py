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
from selenium.webdriver.common.action_chains import ActionChains

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
# 1. 한터차트 (Physical) 크롤러 (Buzz님 검증 코드 완벽 이식)
# ---------------------------------------------------------
def scrape_hanteo_daily(limit=100):
    print("\n" + "="*50)
    print(f"[Hanteo] 피지컬 일간 차트 수집 시작...")
    print("="*50)
    
    driver = None
    hanteo_data = []
    scrape_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        driver = get_driver()
        print("🚀 한터차트 접속 중...")
        driver.get("https://www.hanteochart.com/ko/charts/album/daily")
        time.sleep(12) 
        
        print("🔄 '일간' 탭 활성화 확인...")
        js_find_daily_tab = """
        var tabs = document.querySelectorAll('*');
        for (var i = 0; i < tabs.length; i++) {
            if (tabs[i].textContent && tabs[i].textContent.trim() === '일간') {
                var rect = tabs[i].getBoundingClientRect();
                var isVisible = true;
                var curr = tabs[i];
                while(curr && curr !== document.body) {
                    var compStyle = window.getComputedStyle(curr);
                    if(compStyle.display === 'none' || compStyle.visibility === 'hidden' || parseFloat(compStyle.opacity) === 0) {
                        isVisible = false;
                        break;
                    }
                    curr = curr.parentElement;
                }
                if (isVisible && rect.width > 0) return tabs[i];
            }
        }
        return null;
        """
        try:
            daily_tab = driver.execute_script(js_find_daily_tab)
            if daily_tab:
                ActionChains(driver).move_to_element(daily_tab).click().perform()
                time.sleep(4)
        except Exception:
            pass
            
        js_find_visible_more = """
        var buttons = document.querySelectorAll('button, a, div, span');
        var valid = [];
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            var text = (btn.textContent || '').replace(/\s+/g, '');
            if (text.includes('더보기')) {
                var rect = btn.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                
                var isVisible = true;
                var curr = btn;
                while(curr && curr !== document.body) {
                    var compStyle = window.getComputedStyle(curr);
                    if(compStyle.display === 'none' || compStyle.visibility === 'hidden' || parseFloat(compStyle.opacity) === 0) {
                        isVisible = false;
                        break;
                    }
                    curr = curr.parentElement;
                }
                
                if (isVisible) {
                    valid.push({ el: btn, y: rect.top + window.scrollY });
                }
            }
        }
        
        if (valid.length === 0) return null;
        
        valid.sort((a, b) => a.y - b.y);
        var target = valid[0].el;
        
        var getInnermost = function(node) {
            for (var j = 0; j < node.children.length; j++) {
                var child = node.children[j];
                var cText = (child.textContent || '').replace(/\s+/g, '');
                if (cText.includes('더보기')) {
                    return getInnermost(child);
                }
            }
            return node;
        };
        return getInnermost(target);
        """
        
        for i in range(1, 6):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.4);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.8);")
            time.sleep(2)
            
            target_el = driver.execute_script(js_find_visible_more)
            if target_el:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_el)
                time.sleep(2)
                try:
                    ActionChains(driver).move_to_element(target_el).click().perform()
                except Exception:
                    driver.execute_script("arguments[0].click();", target_el)
                time.sleep(6) 
            else:
                break
                
        print("🔍 최종 데이터 수집 시작 (활성 탭 전용)...")
        js_extract_data = """
        var rows = document.querySelectorAll('div.chart-item.rank-data');
        var result = [];
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            
            var isVisible = true;
            var curr = row;
            while(curr && curr !== document.body) {
                var compStyle = window.getComputedStyle(curr);
                if(compStyle.display === 'none' || compStyle.visibility === 'hidden' || parseFloat(compStyle.opacity) === 0) {
                    isVisible = false;
                    break;
                }
                curr = curr.parentElement;
            }
            
            if (!isVisible) continue;
            
            var leftEl = row.querySelector('div.left');
            var centerEl = row.querySelector('div.center');
            var rightEl = row.querySelector('div.right');
            
            if (!leftEl || !centerEl || !rightEl) continue;
            
            var rankTexts = leftEl.innerText.trim().split('\\n');
            var rank = rankTexts[0];
            if (isNaN(parseInt(rank))) continue;
            
            var centerTexts = centerEl.innerText.trim().split('\\n');
            var artist = centerTexts.length >= 1 ? centerTexts[centerTexts.length - 1] : '';
            var album = centerTexts.length >= 2 ? centerTexts[centerTexts.length - 2] : '';
            
            var rightTexts = rightEl.innerText.trim().split('\\n');
            var index_score = rightTexts.length >= 1 ? rightTexts[rightTexts.length - 1] : '0';
            var sales = rightTexts.length >= 2 ? rightTexts[rightTexts.length - 2] : '0';
            
            result.push([rank, album, artist, sales, index_score]);
            if (result.length >= 100) break;
        }
        return result;
        """
        
        extracted_rows = driver.execute_script(js_extract_data)
        
        if extracted_rows:
            for r in extracted_rows:
                hanteo_data.append({
                    'tab_type': 'physical',
                    'platform': 'hanteo',
                    'rank': r[0],
                    'album': r[1],
                    'artist': r[2],
                    'sales': r[3],
                    'sales_index': r[4], 
                    'scrape_time': scrape_time
                })
            
    except Exception as e:
        print(f"[Hanteo] 에러 발생: {e}")
    finally:
        if driver: driver.quit()
        
    return pd.DataFrame(hanteo_data)

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
        platform = job.get('service', 'unknown')
        limit = job.get('entity_limit', 100)
        hype_weight = job.get('hype_weight', 0)
        
        url = ""
        for key in ['source_urls', 'source_url', 'url', 'target_url', 'link']:
            if key in job:
                val = job[key]
                if isinstance(val, list) and len(val) > 0:
                    url = val[0]
                elif isinstance(val, str):
                    url = val
                break
                
        if not url:
            print(f"\n📡 [{platform}] ⚠️ URL(주소) 항목을 json에서 찾을 수 없어 건너뜁니다.")
            continue
            
        print(f"\n📡 [{platform}] 차트 수집 중... (가중치: {hype_weight})")
        print(f"🔗 접속 주소: {url}")
        
        try:
            # --- 2.1 멜론 일간 차트 (API 정공법 - Requests) ---
            if platform == 'melon':
                res = requests.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                
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

            # --- 2.3 스포티파이 Top 50 (Selenium 렌더링 - 🌟버그 완벽 수정) ---
            elif platform == 'spotify':
                driver = None
                try:
                    driver = get_driver()
                    driver.get(url)
                    time.sleep(6)
                    
                    # 스크롤을 살짝 내려서 곡들이 전부 렌더링되도록 유도
                    for _ in range(5):
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(1)
                        
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    songs = soup.select('div[data-testid="tracklist-row"]')[:limit]
                    for idx, song in enumerate(songs, 1):
                        # 1. 제목: 무조건 internal-track-link 태그로 고정
                        title_el = song.select_one('a[data-testid="internal-track-link"]')
                        title = title_el.text.strip() if title_el else "정보 없음"
                        
                        # 2. 아티스트: 무조건 링크 주소에 '/artist/'가 포함된 태그만 싹쓸이
                        artist_els = song.select('a[href*="/artist/"]')
                        if artist_els:
                            # 듀엣 곡 등 가수가 여러 명일 경우 콤마(,)로 예쁘게 이어붙입니다.
                            artist = ", ".join([a.text.strip() for a in artist_els])
                        else:
                            artist = "정보 없음"
                        
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
    
    physical_df = pd.DataFrame()
    digital_df = pd.DataFrame()
    
    digital_jobs = [job for job in config.get("jobs", []) if job.get("enabled", True) and job.get("service", "") != "hanteo"]
    hanteo_job = next((job for job in config.get("jobs", []) if job.get("enabled", True) and job.get("service", "") == "hanteo"), None)

    # 1. 피지컬 (한터차트) 실행 - 디지털 테스트에만 집중하시려면 이 3줄을 지우거나 주석 처리하시면 훨씬 빨리 끝납니다!
    if hanteo_job:
        physical_df = scrape_hanteo_daily(limit=hanteo_job.get("entity_limit", 100))
        if not physical_df.empty:
            print(f"\n✅ 한터차트 수집 완료: 총 {len(physical_df)} 건")
            physical_df.to_csv("hanteo_test_result.csv", index=False, encoding="utf-8-sig")

    # 2. 디지털 (멜론, 애플, 스포티파이, YTM) 실행
    if digital_jobs:
        digital_df = scrape_digital_charts(digital_jobs)
        if not digital_df.empty:
            print(f"\n✅ 디지털 차트 수집 완료: 총 {len(digital_df)} 건")
            digital_df.to_csv("digital_test_result.csv", index=False, encoding="utf-8-sig")
            print("결과가 digital_test_result.csv 로 안전하게 저장되었습니다.")
        else:
            print("\n❌ 디지털 데이터가 수집되지 않았습니다.")
    else:
        print("\n⚠️ 실행할 디지털 차트 작업이 sync_config.json 에 없습니다.")

if __name__ == "__main__":
    main()
