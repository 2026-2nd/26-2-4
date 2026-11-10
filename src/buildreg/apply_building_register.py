"""건축물대장 응답(building_register_raw.jsonl)으로 v4의 빈 세대수·세대당_주차대수·사용승인일을 채워 v5를 만든다. 2026-11-10.

규칙
- 대상: v4에서 세대수가 빈 거래(lots_to_query.csv와 같은 범위). 키 = (자치구, 법정동, 번지).
- 건물 선택: 사용승인연도가 거래의 건축년도와 ±1년 이내인 건물만 쓴다(같은 번지의 다른 시기 건물·증축동 제외).
  1) 총괄표제부(단지 전체 요약)에 세대수가 있으면 그것을 쓴다. 여러 개면 연도가 맞는 것들을 합친다.
  2) 없으면 표제부(동별)에서 세대수>0인 동의 세대수·주차대수를 합친다.
- 총괄표제부에 사용승인일이 비어 있으면 연도 확인 없이 세대수·주차만 쓰고 사용승인일·연식은 건축년도 기준을 유지한다.
- 사용승인일: 고른 건물 중 가장 이른 날짜. 연식_개월을 이 날짜로 다시 계산한다(계약월 − 사용승인월).
- 주차대수: 옥내·옥외 자주식·기계식 합. 0이면 비워 둔다(미기재와 구분 불가).
- 한 번지에 단지명이 여럿이면 값이 번지 전체 합계이므로 세대수_기준에 '건축물대장(번지 합계)'로 표시한다.
- 못 채운 거래는 결측사유에 이유를 남긴다.
"""
import json, collections, hashlib, pathlib, sys
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / 'data/buildreg/building_register_raw.jsonl'
V4 = ROOT / 'data/final/아파트_실거래_전처리_2017_2026_v4.csv'
V5 = ROOT / 'data/final/아파트_실거래_전처리_2017_2026_v5.csv'
REPORT = ROOT / 'data/buildreg/apply_report.json'
TOL = 1


def num(x):
    try:
        return int(float(str(x).strip() or 0))
    except ValueError:
        return 0


def day(x):
    s = str(x or '').strip()
    return s if len(s) == 8 and s.isdigit() and s[:4] > '1900' else ''


def park(x):
    t = num(x.get('totPkngCnt'))
    s = sum(num(x.get(k)) for k in ('indrAutoUtcnt', 'oudrAutoUtcnt', 'indrMechUtcnt', 'oudrMechUtcnt'))
    return max(t, s)


def pick(rec, year):
    """returns (세대수, 주차, 사용승인일 yyyymmdd, 방법) or (None, None, None, 실패이유)"""
    if rec['상태'] != '성공':
        return None, None, None, '응답 없음' if rec['상태'] == '응답 없음' else '조회 오류'
    recap = [x for x in (rec.get('총괄표제부') or []) if num(x.get('hhldCnt')) > 0]
    title = [x for x in (rec.get('표제부') or []) if num(x.get('hhldCnt')) > 0]
    for src, items in (('총괄표제부', recap), ('표제부', title)):
        if not items:
            continue
        dated = [x for x in items if day(x.get('useAprDay'))]
        ok = [x for x in dated if abs(int(day(x['useAprDay'])[:4]) - year) <= TOL]
        if not dated and src == '총괄표제부':
            # 총괄표제부에 사용승인일이 비어 있으면(오래된 대단지에 많음):
            #  표제부를 받아 둔 번지는 연도가 맞는 동들의 가장 이른 사용승인일을 쓰고,
            #  아니면 연도 확인 없이 세대수·주차만 쓴다(재건축된 번지는 새 대장에 날짜가 있으므로 기존 단지로 본다).
            tdays = [day(x.get('useAprDay')) for x in title if day(x.get('useAprDay'))]
            tok = [t for t in tdays if abs(int(t[:4]) - year) <= TOL]
            if tok:
                return sum(num(x['hhldCnt']) for x in items), sum(park(x) for x in items), min(tok), src
            if tdays:
                continue
            return sum(num(x['hhldCnt']) for x in items), sum(park(x) for x in items), '', '총괄표제부(사용승인일 없음)'
        if ok:
            return sum(num(x['hhldCnt']) for x in ok), sum(park(x) for x in ok), min(day(x['useAprDay']) for x in ok), src
    if not recap and not title:
        return None, None, None, '세대수 기재 없음(공동주택 아님 등)'
    return None, None, None, '사용승인연도 불일치'


def main():
    recs = {}
    for line in open(RAW, encoding='utf-8'):
        r = json.loads(line)
        recs[(r['자치구'], r['법정동'], r['번지'])] = r
    d = pd.read_csv(V4, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    tgt = d.세대수 == ''
    cache, stat, trade_stat = {}, collections.Counter(), collections.Counter()
    hh, pk, ua, how = [], [], [], []
    for idx in d.index[tgt]:
        row = d.loc[idx]
        key = (row.자치구, row.법정동, row.번지)
        y = num(row.건축년도)
        ck = key + (y,)
        if ck not in cache:
            r = recs.get(key)
            cache[ck] = pick(r, y) if r else (None, None, None, '조회 대상 아님')
            stat[cache[ck][3]] += 1
        h, p, u, m = cache[ck]
        trade_stat[m] += 1
        multi = key in recs and ' | ' in recs[key]['단지명']
        hh.append(h); pk.append(p); ua.append(u); how.append((m, multi))
    res = pd.DataFrame({'h': hh, 'p': pk, 'u': ua, 'how': how}, index=d.index[tgt])

    if '세대수_기준' not in d.columns:
        d.insert(d.columns.get_loc('세대수') + 1, '세대수_기준', '')
    d.loc[~tgt & (d.세대수 != ''), '세대수_기준'] = '단지 목록(K-apt)'
    filled = res.h.notna()
    fi = res.index[filled]
    d.loc[fi, '세대수'] = res.loc[fi, 'h'].astype(int).astype(str)
    d.loc[fi, '세대수_기준'] = ['건축물대장(번지 합계)' if mu else '건축물대장' for _, mu in res.loc[fi, 'how']]
    # 주차: 0이면 비움
    pv = res.loc[fi, 'p'].astype(int)
    hv = res.loc[fi, 'h'].astype(int)
    ppos = pv > 0
    d.loc[fi[ppos], '세대당_주차대수'] = (pv[ppos] / hv[ppos]).round(2).astype(str)
    # 사용승인일과 연식_개월
    fi_all = fi
    fi = fi[res.loc[fi, 'u'] != '']
    uv = res.loc[fi, 'u']
    d.loc[fi, '사용승인일'] = uv.str[:4] + '-' + uv.str[4:6] + '-' + uv.str[6:8]
    cm = d.loc[fi, '계약년월'].astype(int)
    months = (cm // 100 * 12 + cm % 100) - (uv.str[:4].astype(int) * 12 + uv.str[4:6].astype(int))
    pre = months < 0
    d.loc[fi, '연식_개월'] = months.where(~pre, 0).astype(str)
    d.loc[fi, '연식_기준'] = '사용승인일'
    d.loc[fi[pre], '연식_개월'] = ''
    d.loc[fi[pre], '연식_기준'] = '준공 전 거래'
    pre_idx = set(fi[pre])

    # 결측사유 갱신
    def fix_reason(s, h_ok, p_ok, why, pre_):
        parts = [x for x in s.split(' / ') if x]
        if h_ok:
            parts = [x for x in parts if not x.startswith('[단지정보]') and not x.startswith('[세대수]')]
            if not p_ok:
                parts = [x for x in parts if not x.startswith('[주차]')] + ['[주차] 건축물대장에 주차대수 미기재']
            else:
                parts = [x for x in parts if not x.startswith('[주차]')]
            parts.append('[난방·복도·시공사] 단지 목록에 없어 미기재(건축물대장에는 항목 없음)')
            if pre_:
                parts.append('[연식_개월] 사용승인일 이전 계약(분양권·입주권 등)')
            if why == '총괄표제부(사용승인일 없음)':
                parts.append('[사용승인일] 건축물대장에 사용승인일 미기재(연식은 건축년도 기준)')
        else:
            parts.append(f'[건축물대장] 채우지 못함: {why}')
        return ' / '.join(parts)

    fi = fi_all
    for idx in res.index:
        h_ok = pd.notna(res.at[idx, 'h'])
        p_ok = h_ok and res.at[idx, 'p'] > 0
        pre_ = h_ok and idx in pre_idx
        d.at[idx, '결측사유'] = fix_reason(d.at[idx, '결측사유'], h_ok, p_ok, res.at[idx, 'how'][0], pre_)

    d.to_csv(V5, index=False, encoding='utf-8-sig')
    out = {
        'rows': len(d), 'target_trades': int(tgt.sum()), 'filled_trades': int(filled.sum()),
        'by_method_trades': dict(trade_stat), 'by_method_lot_year': dict(stat),
        'multi_name_filled_trades': int(sum(mu for _, mu in res.loc[fi, 'how'])),
        'pre_completion_after_fill': int(pre.sum()),
        'missing_pct': {c: round((d[c] == '').mean() * 100, 2) for c in ['세대수', '세대당_주차대수', '사용승인일', '연식_개월', '난방방식', '복도유형', '시공사']},
        'sha256': hashlib.sha256(V5.read_bytes()).hexdigest(),
    }
    REPORT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
