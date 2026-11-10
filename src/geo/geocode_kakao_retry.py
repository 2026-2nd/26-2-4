"""1차 지오코딩에서 '찾지 못함'인 주소만 다시 찾는다 (내 컴퓨터에서 실행).

사용법 (PowerShell, 기계학습팀플 폴더에서):
    $env:KAKAO_REST_API_KEY = "REST API 키"
    python src\\geo\\geocode_kakao_retry.py

시도 순서 (앞에서 찾으면 멈춤). 결과에는 '정밀도'를 함께 남긴다.
 1) 지번주소 유사 검색: 번지가 합쳐지거나 바뀐 경우 → 같은 법정동의 번지 결과만 인정 (정밀도: 지번-유사)
 2) 도로명주소 유사 검색 → 같은 구의 도로명 결과만 인정 (정밀도: 도로명-유사)
 3) 키워드 검색 '동 이름 + 단지명' → 결과 주소가 같은 법정동일 때만 인정 (정밀도: 키워드)
 4) 본번만으로 검색(예: 잠원동 74-1 → 잠원동 74) → 같은 법정동일 때만 인정 (정밀도: 본번)
 5) 그래도 없으면 법정동 중심 좌표 (정밀도: 동중심-근사)
출력: data/geocoding/kakao_geocode_retry.csv
"""
import csv, json, os, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIRST = ROOT / 'data' / 'geocoding' / 'kakao_geocode_results.csv'
OUT = ROOT / 'data' / 'geocoding' / 'kakao_geocode_retry.csv'
ADDR = 'https://dapi.kakao.com/v2/local/search/address.json'
KEYW = 'https://dapi.kakao.com/v2/local/search/keyword.json'
FIELDS = ['지번주소', '도로명주소', '시군구', '번지', '단지명', '건축년도', '거래수', '경도', '위도', '정밀도', '반환주소', '반환이름', '상태']


def get(url, params, key):
    req = urllib.request.Request(url + '?' + urllib.parse.urlencode(params), headers={'Authorization': f'KakaoAK {key}'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode('utf-8')).get('documents', []), ''
    except urllib.error.HTTPError as e:
        return [], {429: 'QUOTA', 401: 'AUTH401', 403: 'AUTH403'}.get(e.code, f'HTTP{e.code}')
    except Exception as e:
        return [], type(e).__name__


def dong_of(d):
    a = d.get('address') or {}
    return a.get('region_3depth_name', '') if a else ''


def gu_of(d):
    a = d.get('road_address') or d.get('address') or {}
    return a.get('region_2depth_name', '') if a else ''


def try_all(row, key):
    sgg = row['시군구'].split()
    gu, dong = sgg[1], sgg[2]
    main_no = row['번지'].split('-')[0]
    steps = [
        ('지번-유사', ADDR, {'query': row['지번주소'], 'analyze_type': 'similar', 'size': 10},
         lambda d: d.get('address_type') == 'REGION_ADDR' and dong_of(d) == dong),
        ('도로명-유사', ADDR, {'query': row['도로명주소'], 'analyze_type': 'similar', 'size': 10},
         lambda d: d.get('address_type') == 'ROAD_ADDR' and gu_of(d) == gu) if row['도로명주소'] else None,
        ('키워드', KEYW, {'query': f"{dong} {row['단지명']}", 'size': 15},
         lambda d: f' {dong} ' in f" {d.get('address_name', '')} "),
        ('본번', ADDR, {'query': f"{row['시군구']} {main_no}", 'analyze_type': 'exact', 'size': 10},
         lambda d: d.get('address_type') == 'REGION_ADDR' and dong_of(d) == dong) if main_no != row['번지'] else None,
        ('동중심-근사', ADDR, {'query': row['시군구'], 'analyze_type': 'exact', 'size': 5},
         lambda d: d.get('address_type') == 'REGION'),
    ]
    for step in steps:
        if step is None:
            continue
        label, url, params, ok = step
        docs, err = get(url, params, key)
        if err in ('QUOTA', 'AUTH401', 'AUTH403'):
            return None, err
        time.sleep(0.12)
        for d in docs:
            if ok(d):
                return {'경도': f"{float(d['x']):.7f}", '위도': f"{float(d['y']):.7f}", '정밀도': label,
                        '반환주소': d.get('address_name', ''), '반환이름': d.get('place_name', ''), '상태': '성공'}, ''
    return {'상태': '찾지 못함'}, ''


def main():
    key = os.environ.get('KAKAO_REST_API_KEY', '').strip()
    if not key:
        sys.exit('환경변수 KAKAO_REST_API_KEY가 없습니다.')
    rows = [x for x in csv.DictReader(open(FIRST, encoding='utf-8-sig')) if x['상태'] != '성공']
    print(f'재시도 대상 {len(rows)}개')
    with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i, row in enumerate(rows, 1):
            res, stop = try_all(row, key)
            if stop:
                print(f'중단: {stop}')
                break
            out = {k: row.get(k, '') for k in ['지번주소', '도로명주소', '시군구', '번지', '단지명', '건축년도', '거래수']}
            out.update(res)
            w.writerow(out)
            print(f"{i}/{len(rows)} {row['단지명']}: {res.get('정밀도', res['상태'])} {res.get('반환이름', '')}")
    print(f'완료. 결과: {OUT}')


if __name__ == '__main__':
    main()
