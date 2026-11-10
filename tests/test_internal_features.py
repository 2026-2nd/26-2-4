"""Identity and historical-leakage guards; artificial fixtures only."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'/'pipeline'))
from build_internal_features import make_indexes,match,attach,snapshot_values
def complex_fixture(**changes):
 r={'k-아파트코드':'TEST','k-아파트명':'테스트아파트','kapt도로명주소':'서울특별시 강남구 테스트로 1','주소(시군구)':'강남구','주소(읍면동)':'테스트동','k-사용검사일-사용승인일':'2001-01-01','k-수정일자':'2026-10-31','k-전체세대수':'100','주차대수':'150','k-난방방식':'지역난방','k-복도유형':'혼합식'};r.update(changes);return r
def transaction(**changes):
 r={'시군구':'서울특별시 강남구 테스트동','번지':'1','단지명':'테스트','도로명':'테스트로 1','건축년도':'2001','contract_date':'2020-01-01'};r.update(changes);return r
class InternalGuards(unittest.TestCase):
 def test_current_snapshot_never_backfilled(self):
  rows=[complex_fixture()];r=transaction();matched=match(r,rows,make_indexes(rows));out=attach(r,matched,rows,'2026-11-01')
  self.assertEqual(out['household_count_snapshot'],'100');self.assertEqual(out['household_count'],'');self.assertEqual(out['complex_match_status'],'address_name_supported')
 def test_ambiguous_address_not_arbitrarily_selected(self):
  rows=[complex_fixture(),complex_fixture(**{'k-아파트코드':'TEST2'})];r=match(transaction(),rows,make_indexes(rows));self.assertIsNone(r['selected'])
 def test_future_complex_attributes_not_attached(self):
  rows=[complex_fixture(**{'k-사용검사일-사용승인일':'2021-01-01'})];r=transaction();out=attach(r,match(r,rows,make_indexes(rows)),rows,'2026-11-01');self.assertEqual(out['household_count_snapshot'],'');self.assertEqual(out['internal_feature_status'],'unavailable_preapproval')
 def test_zero_households_and_parking_not_converted_to_ratio(self):
  out,issues=snapshot_values(complex_fixture(**{'k-전체세대수':'0','주차대수':'0'}));self.assertEqual(out['parking_per_household_snapshot'],'');self.assertIn('households_missing_or_nonpositive',issues)
 def test_same_name_other_district_not_matched(self):
  rows=[complex_fixture()];r=match(transaction(시군구='서울특별시 서초구 테스트동'),rows,make_indexes(rows));self.assertIsNone(r['selected'])
if __name__=='__main__':unittest.main()
