"""카카오 로컬 API로 지오코딩 대상 주소 6,721개에 좌표를 붙인다 (내 컴퓨터에서 실행).

사용법 (PowerShell, 기계학습팀플 폴더에서):
    $env:KAKAO_REST_API_KEY = "REST API 키"
    python src\\geo\\geocode_kakao.py

- 입력: 지오코딩_대상_주소_2017_2026.csv (폴더 최상단 또는 data/final/)
- 출력: data/geocoding/kakao_geocode_results.csv
  중간에 끊겨도 다시 실행하면 이미 처리한 주소는 건너뛰고 이어서 한다.
- 순서: 지번주소로 먼저 찾는다(실거래 자료의 기준 주소가 지번이므로).
  번지까지 정확히 맞지 않으면 도로명주소로 다시 찾는다.
  둘 다 찾으면 두 좌표 사이 거리를 기록해 검증에 쓴다.
- 키는 환경변수에서만 읽고, 파일이나 화면에 남기지 않는다.
- 외부 패키지 없이 파이썬 기본 라이브러리만 쓴다.
"""
import csv, json, math, os, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = [ROOT / '지오코딩_대상_주소_2017_2026.csv', ROOT / 'data' / 'final' / '지오코딩_대상_주소_2017_2026.csv']
OUT = ROOT / 'data' / 'geocoding' / 'kakao_geocode_results.csv'
URL = 'https://dapi.kakao.com/v2/local/search/address.json'
FIELDS = ['지번주소', '도로명주소', '시군구', '번지', '단지명', '건축년도', '거래수',
          '경도', '위도', '좌표기준', '결과유형', '반환주소', '지번_도로명_거리m', '상태']
SLEEP = 0.12          # 초당 약 8회
MAX_RETRY = 3


def call(query, key):
    """returns (documents list, error string or '')"""
    url = URL + '?' + urllib.parse.urlencode({'query': query, 'analyze_type': 'exact', 'size': 5})
    req = urllib.request.Request(url, headers={'Authorization': f'KakaoAK {key}'})
    for attempt in range(MAX_RETRY):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode('utf-8')).get('documents', []), ''
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return [], 'QUOTA'            # 쿼터 소진: 중단
            if e.code in (401, 403):
                return [], f'AUTH{e.code}'    # 키·카카오맵 사용 설정 문제: 중단
            err = f'HTTP{e.code}'
        except Exception as e:  # network
            err = type(e).__name__
        time.sleep(1.5 * (attempt + 1))
    return [], err


def pick(docs, want):
    """want='jibun'|'road'. returns (lon, lat, type, address) of the best exact match or None"""
    for d in docs:
        t = d.get('address_type', '')
        if want == 'jibun' and t == 'REGION_ADDR':
            return float(d['x']), float(d['y']), t, d.get('address_name', '')
        if want == 'road' and t == 'ROAD_ADDR':
            return float(d['x']), float(d['y']), t, d.get('address_name', '')
    return None


def dist_m(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def geocode(row, key):
    out = {k: row.get(k, '') for k in ['지번주소', '도로명주소', '시군구', '번지', '단지명', '건축년도', '거래수']}
    j = r = None
    docs, err = call(row['지번주소'], key)
    if err in ('QUOTA',) or err.startswith('AUTH'):
        return None, err
    j = pick(docs, 'jibun')
    if row.get('도로명주소'):
        time.sleep(SLEEP)
        docs2, err2 = call(row['도로명주소'], key)
        if err2 in ('QUOTA',) or err2.startswith('AUTH'):
            return None, err2
        r = pick(docs2, 'road')
    best = j or r
    if best is None:
        out.update(상태='찾지 못함' + (f'({err})' if err else ''))
        return out, ''
    out.update(경도=f'{best[0]:.7f}', 위도=f'{best[1]:.7f}', 좌표기준='지번' if j else '도로명',
               결과유형=best[2], 반환주소=best[3], 상태='성공')
    if j and r:
        out['지번_도로명_거리m'] = f'{dist_m(j, r):.0f}'
    return out, ''


def main():
    key = os.environ.get('KAKAO_REST_API_KEY', '').strip()
    if not key:
        sys.exit('환경변수 KAKAO_REST_API_KEY가 없습니다. PowerShell: $env:KAKAO_REST_API_KEY = "키"')
    src = next((p for p in CANDIDATES if p.exists()), None)
    if src is None:
        sys.exit('지오코딩_대상_주소_2017_2026.csv 를 찾지 못했습니다.')
    rows = list(csv.DictReader(open(src, encoding='utf-8-sig')))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        done = {x['지번주소'] for x in csv.DictReader(open(OUT, encoding='utf-8-sig')) if x.get('상태')}
    todo = [x for x in rows if x['지번주소'] not in done]
    print(f'대상 {len(rows)}개, 이미 처리 {len(done)}개, 이번에 처리 {len(todo)}개')
    new = not OUT.exists()
    with open(OUT, 'a', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        ok = fail = 0
        for i, row in enumerate(todo, 1):
            res, stop = geocode(row, key)
            if stop:
                msg = {'QUOTA': '오늘 무료 호출 한도를 다 썼습니다. 내일 다시 실행하면 이어서 합니다.',
                       'AUTH401': '키가 잘못됐습니다. REST API 키인지 확인하세요.',
                       'AUTH403': '권한이 없습니다. 앱의 [카카오맵] 사용 설정이 ON인지 확인하세요.'}.get(stop, stop)
                print(f'\n중단: {msg} (처리 {i - 1}개 저장됨)')
                break
            w.writerow(res); f.flush()
            ok += res['상태'] == '성공'; fail += res['상태'] != '성공'
            if i % 200 == 0 or i == len(todo):
                print(f'{i}/{len(todo)}  성공 {ok}  실패 {fail}')
            time.sleep(SLEEP)
    print(f'완료. 결과: {OUT}')


if __name__ == '__main__':
    main()
