"""건축물대장(국토교통부 건축HUB)에서 단지정보가 비어 있는 번지 7,068개의 세대수·주차대수·사용승인일을 받는다.
내 컴퓨터에서 실행한다. (v2, 2026-11-09)

사용법 (PowerShell, 기계학습팀플 폴더에서):
    $env:DATA_GO_KR_KEY = "공공데이터포털 일반 인증키(Decoding)"
    $env:KAKAO_REST_API_KEY = "카카오 REST API 키"     # 법정동코드 확인용(이미 받았으면 없어도 됨)
    python src\\buildreg\\fetch_building_register.py

- 입력: data/buildreg/lots_to_query.csv
- 출력:
    data/buildreg/bjdong_codes.csv            (법정동 → 10자리 법정동코드)
    data/buildreg/building_register_raw.jsonl (번지별 응답에서 필요한 항목만, 한 줄 = 번지 1개)
    data/buildreg/fetch_log.txt               (진행 상황과 멈춘 이유)
- v2 변경
    * 총괄표제부를 먼저 받고, 없거나 세대수가 0일 때만 표제부를 받는다(호출 수 약 절반).
    * 표제부는 100개 넘게 있으면 다음 쪽까지 받는다.
    * 응답이 깨져도 그 번지만 '오류'로 적고 계속한다. 멈춘 이유는 fetch_log.txt에 남긴다.
    * 10개마다 진행 상황을 출력한다.
- 중간에 끊겨도 다시 실행하면 이미 받은 번지는 건너뛴다.
- 키는 환경변수에서만 읽고 파일·화면에 남기지 않는다. 파이썬 기본 라이브러리만 쓴다.
"""
import csv, json, os, sys, time, traceback, urllib.parse, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'data' / 'buildreg'
# 추가 조회: python src\\buildreg\\fetch_building_register.py 2  → lots_to_query_2.csv / building_register_raw_2.jsonl
SUFFIX = f'_{sys.argv[1]}' if len(sys.argv) > 1 else ''
LOTS = D / f'lots_to_query{SUFFIX}.csv'
CODES = D / 'bjdong_codes.csv'
RAW = D / f'building_register_raw{SUFFIX}.jsonl'
LOG = D / f'fetch_log{SUFFIX}.txt'
HUB = 'https://apis.data.go.kr/1613000/BldRgstHubService/'
KAKAO = 'https://dapi.kakao.com/v2/local/search/address.json'
SLEEP = 0.15
ROWS = 100
KEEP = ['bldNm', 'dongNm', 'mainPurpsCdNm', 'etcPurps', 'hhldCnt', 'hoCnt', 'fmlyCnt', 'mainBldCnt',
        'totPkngCnt', 'indrAutoUtcnt', 'oudrAutoUtcnt', 'indrMechUtcnt', 'oudrMechUtcnt',
        'useAprDay', 'pmsDay', 'stcnsDay', 'regstrKindCdNm', 'mgmBldrgstPk', 'grndFlrCnt']


def log(msg):
    line = f'[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}'
    print(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


class Stop(Exception):
    pass


def http_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    err = ''
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                txt = r.read().decode('utf-8', errors='replace')
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise Stop('호출 한도 초과(429). 내일 다시 실행하면 이어서 합니다.')
            if e.code in (401, 403):
                raise Stop(f'인증 실패(HTTP {e.code}). 키를 확인하세요.')
            err = f'HTTP{e.code}'
        except Exception as e:
            err = type(e).__name__
        time.sleep(3 * (attempt + 1))
    else:
        return None, err
    s = txt.lstrip()
    if s.startswith('<'):          # 공공데이터포털 오류는 XML로 온다
        if 'SERVICE_KEY_IS_NOT_REGISTERED' in s or 'SERVICE KEY IS NOT REGISTERED' in s:
            raise Stop('인증키가 아직 등록되지 않았습니다. Decoding 키인지 확인하세요.')
        if 'LIMITED_NUMBER_OF_SERVICE_REQUESTS' in s:
            raise Stop('오늘 호출 한도를 다 썼습니다. 내일 다시 실행하면 이어서 합니다.')
        return None, 'XML:' + s[:150].replace('\n', ' ')
    try:
        return json.loads(s), ''
    except ValueError:
        return None, 'JSON아님:' + s[:150].replace('\n', ' ')


def bjdong_codes(dongs, kkey):
    have = {}
    if CODES.exists():
        have = {(r['자치구'], r['법정동']): r['법정동코드'] for r in csv.DictReader(open(CODES, encoding='utf-8-sig'))}
    todo = [x for x in dongs if not have.get(x)]
    if todo and not kkey:
        raise Stop(f'법정동코드 {len(todo)}개 확인에 KAKAO_REST_API_KEY가 필요합니다.')
    for gu, dong in todo:
        q = urllib.parse.urlencode({'query': f'서울특별시 {gu} {dong}', 'analyze_type': 'exact'})
        js, err = http_json(f'{KAKAO}?{q}', {'Authorization': f'KakaoAK {kkey}'})
        code = ''
        for d in (js or {}).get('documents', []):
            a = d.get('address') or {}
            if a.get('b_code') and a.get('region_3depth_name') == dong:
                code = a['b_code']; break
        have[(gu, dong)] = code
        time.sleep(SLEEP)
    if todo:
        with open(CODES, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f); w.writerow(['자치구', '법정동', '법정동코드'])
            for (gu, dong), c in sorted(have.items()):
                w.writerow([gu, dong, c])
    miss = [k for k, v in have.items() if not v]
    log(f'법정동코드 {len(have) - len(miss)}/{len(have)}개 확인' + (f', 못 찾음: {miss}' if miss else ''))
    return have


def body(js):
    try:
        b = js['response']['body']
    except (KeyError, TypeError):
        return None, 0
    it = b.get('items')
    total = int(b.get('totalCount') or 0)
    if not it:
        return [], total
    it = it.get('item', []) if isinstance(it, dict) else it
    return (it if isinstance(it, list) else [it]), total


def fetch(op, code10, bunji, dkey):
    """returns (items or None, error, calls)"""
    plat = '1' if bunji.startswith('산') else '0'
    b = bunji.removeprefix('산')
    bun, _, ji = b.partition('-')
    out, page, calls = [], 1, 0
    while True:
        p = {'serviceKey': dkey, 'sigunguCd': code10[:5], 'bjdongCd': code10[5:], 'platGbCd': plat,
             'bun': bun.zfill(4), 'ji': (ji or '0').zfill(4), '_type': 'json',
             'numOfRows': str(ROWS), 'pageNo': str(page)}
        js, err = http_json(HUB + op + '?' + urllib.parse.urlencode(p)); calls += 1
        time.sleep(SLEEP)
        if js is None:
            return None, err, calls
        it, total = body(js)
        if it is None:
            hdr = (js.get('response') or {}).get('header') or {}
            code, msg = str(hdr.get('resultCode', '')), str(hdr.get('resultMsg', ''))
            if code == '22' or 'LIMITED' in msg.upper():
                raise Stop('오늘 호출 한도를 다 썼습니다. 내일 다시 실행하면 이어서 합니다.')
            if code in ('30', '31'):
                raise Stop(f'인증 문제({code}:{msg}). 키를 확인하세요.')
            return None, f'{code}:{msg}', calls
        out += [{k: x.get(k) for k in KEEP} for x in it]
        if len(out) >= total or not it or page >= 20:
            return out, '', calls
        page += 1


def need_title(recap):
    if not recap:
        return True
    return sum(int(x.get('hhldCnt') or 0) for x in recap) == 0


def main():
    dkey = os.environ.get('DATA_GO_KR_KEY', '').strip()
    kkey = os.environ.get('KAKAO_REST_API_KEY', '').strip()
    if not dkey:
        sys.exit('환경변수 DATA_GO_KR_KEY가 없습니다.')
    lots = list(csv.DictReader(open(LOTS, encoding='utf-8-sig')))
    done = set()
    if RAW.exists():
        for line in open(RAW, encoding='utf-8'):
            if line.strip():
                r = json.loads(line); done.add((r['자치구'], r['법정동'], r['번지']))
    todo = [x for x in lots if (x['자치구'], x['법정동'], x['번지']) not in done]
    log(f'시작: 대상 번지 {len(lots)}개, 처리됨 {len(done)}개, 이번에 {len(todo)}개')
    calls = ok = bad = 0
    i = 0
    try:
        codes = bjdong_codes(sorted({(x['자치구'], x['법정동']) for x in lots}), kkey)
        with open(RAW, 'a', encoding='utf-8') as f:
            for i, x in enumerate(todo, 1):
                code = codes.get((x['자치구'], x['법정동']), '')
                rec = {k: x[k] for k in ['자치구', '법정동', '번지', '단지명', '건축년도', '거래수']}
                rec['법정동코드'] = code
                if not code:
                    rec['상태'] = '법정동코드 없음'
                else:
                    try:
                        recap, e1, c1 = fetch('getBrRecapTitleInfo', code, x['번지'], dkey); calls += c1
                        title, e2 = None, ''
                        if need_title(recap):
                            title, e2, c2 = fetch('getBrTitleInfo', code, x['번지'], dkey); calls += c2
                        rec.update(총괄표제부=recap, 표제부=title, 오류='; '.join(e for e in (e1, e2) if e))
                        rec['상태'] = '성공' if (recap or title) else ('응답 없음' if not rec['오류'] else '오류')
                    except Stop:
                        raise
                    except Exception as e:
                        rec.update(상태='오류', 오류=f'{type(e).__name__}: {e}'[:200])
                ok += rec['상태'] == '성공'; bad += rec['상태'] == '오류'
                f.write(json.dumps(rec, ensure_ascii=False) + '\n'); f.flush()
                if i % 10 == 0 or i == len(todo):
                    print(f'{i}/{len(todo)}  성공 {ok}  오류 {bad}  호출 {calls}', flush=True)
                if i % 500 == 0:
                    log(f'진행 {i}/{len(todo)}, 성공 {ok}, 오류 {bad}, 호출 {calls}')
        log(f'완료: 이번에 {i}개 처리, 성공 {ok}, 오류 {bad}, 호출 {calls}')
    except Stop as s:
        log(f'중단: {s} (이번에 {i - 1 if i else 0}개 저장, 호출 {calls})')
    except KeyboardInterrupt:
        log(f'사용자가 멈춤(Ctrl+C) (이번에 {i}개 근처까지 저장, 호출 {calls})')
    except Exception:
        log('예상하지 못한 오류로 멈춤:\n' + traceback.format_exc())
    print(f'결과: {RAW}\n기록: {LOG}')


if __name__ == '__main__':
    main()
