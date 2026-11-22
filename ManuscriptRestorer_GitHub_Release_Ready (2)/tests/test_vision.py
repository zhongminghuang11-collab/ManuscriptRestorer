import unittest
from vision_adapter import ground_suggestions
class VisionTest(unittest.TestCase):
    def test_ground_one_unique(self):
        r=ground_suggestions({'suggested_edits':[{'op':'replace','original':'很好','replacement':'不错','evidence':'有红字'}]},
                             [{'id':'t1','text':'今天天气很好','line':0}])
        self.assertEqual(r['proposals'][0]['span'],[4,6]);self.assertEqual(r['proposals'][0]['status'],'proposed')
    def test_reject_ambiguous(self):
        r=ground_suggestions({'suggested_edits':[{'op':'delete','original':'今天','replacement':''}]},
                             [{'id':'t1','text':'今天今天'}])
        self.assertEqual(len(r['proposals']),0);self.assertEqual(len(r['unmatched']),1)
    def test_reject_unmatched(self):
        r=ground_suggestions({'suggested_edits':[{'op':'delete','original':'明天','replacement':''}]},
                             [{'id':'t1','text':'今天'}])
        self.assertEqual(len(r['unmatched']),1)
    def test_insert_anchor(self):
        r=ground_suggestions({'suggested_edits':[{'op':'insert_after','original':'天气','replacement':'真'}]},
                             [{'id':'t1','text':'今天天气好'}])
        self.assertEqual(r['proposals'][0]['span'],[4,4])

if __name__=='__main__':unittest.main()
