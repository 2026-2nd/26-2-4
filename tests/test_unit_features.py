"""Date and missing-value guards with artificial fixtures, not research records."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'/'pipeline'))
from build_unit_features import derive
def fixture(**kwargs):
 row={'계약년월':'202002','계약일':'29','전용면적(㎡)':'84.9700','층':'12','건축년도':'2001'};row.update(kwargs);return row
class UnitFeatureGuards(unittest.TestCase):
 def test_age_is_contract_year_not_collection_year(self):
  r=derive(fixture());self.assertEqual(r['building_age_years'],19);self.assertEqual(r['age_basis'],'build_year_approx')
 def test_future_build_year_does_not_create_negative_age(self):
  r=derive(fixture(건축년도='2021'));self.assertEqual(r['building_age_years'],'');self.assertIn('build_year_after_contract_year',r['unit_feature_issues'])
 def test_invalid_day_does_not_get_rounded(self):
  r=derive(fixture(계약일='30'));self.assertEqual(r['contract_date'],'');self.assertEqual(r['building_age_years'],'')
 def test_basement_retained_for_review(self):
  r=derive(fixture(층='-1'));self.assertEqual(r['transaction_floor'],-1);self.assertEqual(r['unit_feature_status'],'complete_with_review')
 def test_nonfinite_or_zero_area_not_accepted(self):
  for value in ['NaN','Infinity','0','-1','']:
   r=derive(fixture(**{'전용면적(㎡)':value}));self.assertEqual(r['exclusive_area_m2'],'')
if __name__=='__main__':unittest.main()
