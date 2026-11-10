"""Guard conditional backfill and provenance using artificial fixtures."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'/'pipeline'))
from apply_internal_static_assumption import transform
from build_internal_features import FEATURES
POLICY={'version':'test','eligible_match_status':['address_name_supported'],'known_change_risk_exclusions':[{'kapt_code':'TEST','feature':'heating_type'}]}
def source():return {'k-사용검사일-사용승인일':'2001-01-01','k-전체동수':'5'}
def row(**changes):
 r={'complex_match_status':'address_name_supported','complex_candidate_kapt_code':'TEST','contract_date':'2020-01-01','건축년도':'2001','internal_feature_issues':'no_verified_attribute_history'}
 r.update({f:'' for f in FEATURES});r.update({f+'_snapshot':'1' for f in FEATURES});r.update(changes);return r
class StaticAssumptionGuards(unittest.TestCase):
 def test_fill_is_assumed_and_strict_value_retained(self):
  out=transform(row(),source(),POLICY);self.assertEqual(out['corridor_type'],'1');self.assertEqual(out['corridor_type_basis'],'assumed_time_invariant');self.assertEqual(out['corridor_type_history_verified'],'')
 def test_known_change_risk_remains_missing(self):
  out=transform(row(),source(),POLICY);self.assertEqual(out['heating_type'],'');self.assertEqual(out['heating_type_basis'],'excluded_known_change_risk')
 def test_address_only_candidate_not_filled(self):
  out=transform(row(complex_match_status='unique_address_review'),source(),POLICY);self.assertEqual(out['corridor_type'],'')
 def test_preapproval_not_filled(self):
  out=transform(row(contract_date='2000-01-01'),source(),POLICY);self.assertEqual(out['household_count'],'')
 def test_missing_building_count_not_assumed_constant(self):
  s=source();s['k-전체동수']='0';out=transform(row(),s,POLICY);self.assertEqual(out['parking_per_household'],'')
if __name__=='__main__':unittest.main()
