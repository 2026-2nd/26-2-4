"""Adversarial identity fixtures: avoid phase, rental, parcel and generic-name merges."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'/'pipeline'))
from improve_complex_crosswalk import evaluate,parcel
def tx(**changes):
 r={'시군구':'서울특별시 송파구 잠실동','번지':'22','단지명':'리센츠','도로명':'테스트로 1','건축년도':'2008'};r.update(changes);return r
def source(**changes):
 r={'주소(시군구)':'송파구','주소(읍면동)':'잠실동','k-사용검사일-사용승인일':'2008-01-01','k-아파트명':'잠실리센츠','kapt도로명주소':'서울특별시 송파구 테스트로 1','나머지주소':''};r.update(changes);return r
class CrosswalkGuards(unittest.TestCase):
 def test_prefix_alias_with_address_year(self):self.assertEqual(evaluate(tx(),source())['method'],'road_year_name_alias_supported')
 def test_phase_conflict_even_same_address_and_year(self):self.assertFalse(evaluate(tx(단지명='주공1단지'),source(**{'k-아파트명':'주공2단지','나머지주소':'22'}))['method'])
 def test_combined_complex_is_not_same_as_one_phase(self):self.assertFalse(evaluate(tx(단지명='푸르지오2단지'),source(**{'k-아파트명':'푸르지오2,3단지','나머지주소':'22'}))['method'])
 def test_explicit_wrong_parcel_blocks_alias(self):self.assertFalse(evaluate(tx(),source(**{'나머지주소':'23'}))['method'])
 def test_rental_and_private_not_merged(self):self.assertFalse(evaluate(tx(),source(**{'k-아파트명':'리센츠임대','나머지주소':'22'}))['method'])
 def test_generic_brand_not_enough_without_parcel(self):self.assertFalse(evaluate(tx(단지명='현대'),source(**{'k-아파트명':'잠실현대'}))['method'])
 def test_building_number_is_not_parcel(self):self.assertIsNone(parcel('101동 관리사무소'));self.assertEqual(parcel('22번지 관리사무소'),(False,22,0))
 def test_builder_subcomplex_not_promoted(self):self.assertFalse(evaluate(tx(단지명='관악드림(동아)'),source(**{'k-아파트명':'관악드림타운','나머지주소':'22'}))['method'])
if __name__=='__main__':unittest.main()
