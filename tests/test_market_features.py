"""Artificial date/address fixtures only; these are not research observations."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'/'pipeline'))
from build_market_features import derive
MAPPING={'중구':'11140','중랑구':'11260'}
def fixture(**values):
 row={'시군구':'서울특별시 중랑구 면목동','contract_date':'2020-01-01','계약년월':'202001','계약일':'1'};row.update(values);return row
class MarketControls(unittest.TestCase):
 def test_exact_district_token_not_substring(self):
  value=derive(fixture(),MAPPING);self.assertEqual(value['district_code'],'11260');self.assertEqual(value['contract_time_index'],0)
 def test_year_rollover(self):
  value=derive(fixture(contract_date='2021-01-01',계약년월='202101'),MAPPING);self.assertEqual(value['contract_time_index'],12)
 def test_conflicting_date_not_silently_used(self):
  value=derive(fixture(계약년월='202002'),MAPPING);self.assertEqual(value['contract_month'],'');self.assertIn('source_conflict',value['market_feature_issues'])
 def test_unmapped_district_keeps_time_features(self):
  value=derive(fixture(시군구='부산광역시 중구 중앙동'),MAPPING);self.assertEqual(value['district_code'],'');self.assertEqual(value['contract_month'],1)
if __name__=='__main__':unittest.main()
