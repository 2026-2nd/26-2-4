import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'/'pipeline'))
from improve_complex_crosswalk_v3 import evaluate,base_name
def tx(name,road='',year='1988',addr='서울특별시 노원구 상계동',bunji='100'):
 return {'시군구':addr,'번지':bunji,'단지명':name,'도로명':road,'건축년도':year}
def src(name,road='서울특별시 노원구 동일로 1',year='1988',dong='상계동',parcel=''):
 return {'주소(시군구)':'노원구','주소(읍면동)':dong,'kapt도로명주소':road,'나머지주소':parcel,'k-아파트명':name,'k-사용검사일-사용승인일':f'{year}-05-01 00:00:00.0'}
class V3Rules(unittest.TestCase):
 def test_geo_prefix_generic_only_with_unique_road(self):
  e=evaluate(tx('한신','동일로 1'),src('상계한신'),1);self.assertEqual(e['method'],'road_year_geo_prefix_supported')
 def test_geo_prefix_needs_unique_road_candidate(self):
  e=evaluate(tx('한신','동일로 1'),src('상계한신'),2);self.assertEqual(e['method'],'')
 def test_phase_conflict_blocks(self):
  e=evaluate(tx('상계주공4(고층)','다른로 9'),src('상계주공5단지'),1);self.assertEqual(e['method'],'')
 def test_dong_year_phase_name(self):
  e=evaluate(tx('상계주공4(고층)','다른로 9'),src('상계주공4단지'),1);self.assertEqual(e['method'],'dong_year_phase_name_supported')
 def test_dong_year_generic_only_without_phase_rejected(self):
  e=evaluate(tx('삼성래미안','다른로 9'),src('상계삼성래미안'),1);self.assertEqual(e['method'],'')
 def test_year_mismatch_without_road_rejected(self):
  e=evaluate(tx('상계주공4(고층)','다른로 9',year='1989'),src('상계주공4단지'),1);self.assertEqual(e['method'],'')
 def test_off_by_one_needs_road(self):
  self.assertEqual(evaluate(tx('은마','동일로 1',year='1980'),src('은마',year='1979'),1)['method'],'road_name_year_off_by_one_supported')
  self.assertEqual(evaluate(tx('은마','다른로 1',year='1980'),src('은마',year='1979'),1)['method'],'')
 def test_rental_mismatch_blocks(self):
  self.assertEqual(evaluate(tx('신내9','동일로 1'),src('신내9단지임대'),1)['method'],'')
 def test_subcomplex_is_location_only(self):
  self.assertEqual(evaluate(tx('파크뷰자이1단지','동일로 1'),src('파크뷰자이아파트'),1)['method'],'road_year_subcomplex_scope_location_only')
 def test_other_district_ignored(self):
  s=src('상계한신');s['주소(시군구)']='도봉구';self.assertIsNone(evaluate(tx('한신','동일로 1'),s,1))
 def test_base_name_strips_phase_and_prefix(self):
  self.assertEqual(base_name('상계주공4(고층)','노원구','상계동'),'주공')
if __name__=='__main__':unittest.main()
