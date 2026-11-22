import unittest
from evaluate import distance,cer,evaluate
class EvaluateTest(unittest.TestCase):
    def test_distance(self):
        self.assertEqual(distance('你好世界','你好人间'),2)
        self.assertEqual(distance('abc','ac'),1)
    def test_cer(self):
        self.assertEqual(cer('你好','你们')['cer'],.5)
    def test_document(self):
        doc={'pages':[{'tokens':[{'id':'t','text':'你好','line':0,'order':0}],
                       'edits':[{'id':'e','op':'replace','span':[1,2],'target_id':'t','text':'们','status':'confirmed'}]}]}
        result=evaluate(doc,{'original':'你好','final':'你们'})
        self.assertEqual(result['final']['cer'],0)
if __name__=='__main__':unittest.main()
