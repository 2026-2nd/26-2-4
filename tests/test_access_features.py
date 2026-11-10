import pathlib,sys,unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'/'pipeline'))
from build_access_features import service_line,hav,stations,schools
class Access(unittest.TestCase):
 def test_haversine_known_distance(self):
  d=hav(np.array([37.5]),np.array([127.0]),np.array([37.509]),np.array([127.0]))[0,0]
  self.assertAlmostEqual(d,1000.8,delta=1.5)
 def test_service_line_merges_branches_and_operators(self):
  self.assertEqual(service_line('S1121','2호선','용답'),'L2')
  self.assertEqual(service_line('S4108','수도권 광역철도 8호선','별내역'),'L8')
  self.assertEqual(service_line('I4102','경원선','이촌역'),'GJ')
  self.assertEqual(service_line('I4102','경원선','창동역'),'L1')
  self.assertEqual(service_line('I4108','경춘선','상봉역'),'GC')
 def test_new_stations_have_event_dates(self):
  st={(s['name'],s['line']):s for s in stations()}
  self.assertEqual(st[('관악산','SILLIM')]['open'],'2022-05-28')
  self.assertEqual(st[('암사역사공원','L8')]['open'],'2024-08-10')
  self.assertEqual(st[('서울역(GTX-A)','GTXA')]['open'],'2024-12-28')
  self.assertEqual(st[('강남','L2')]['basis'],'assumed_open_before_2020')
 def test_closed_school_window(self):
  sc={s['name']:s for s in schools()}
  self.assertEqual(sc['서울염강초등학교']['close'],'2020-03-01')
  self.assertEqual(sc['화양초등학교']['close'],'2023-03-01')
if __name__=='__main__':unittest.main()
