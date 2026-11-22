import unittest
from core import ManuscriptError, reconstruct, reconstruct_document

class CoreTest(unittest.TestCase):
    def make(self, text='你好世界'):
        return {'tokens':[{'id':'t','text':text,'line':0,'order':0}], 'edits':[]}
    def op(self,op,span,text='',status='confirmed',eid='e'):
        return {'id':eid,'target_id':'t','op':op,'span':span,'text':text,'status':status}
    def test_no_edits(self):
        d=reconstruct(self.make());self.assertEqual(d['original'],'你好世界');self.assertEqual(d['final'],'你好世界')
    def test_partial_replace(self):
        d=self.make();d['edits']=[self.op('replace',[2,4],'人间')]
        x=reconstruct(d);self.assertEqual(x['original'],'你好世界');self.assertEqual(x['final'],'你好人间')
    def test_insert_around_replace(self):
        d=self.make();d['edits']=[self.op('insert_before',[2,2],'美丽的',eid='a'),self.op('replace',[2,4],'人间',eid='b'),self.op('insert_after',[4,4],'！',eid='c')]
        self.assertEqual(reconstruct(d)['final'],'你好美丽的人间！')
    def test_nonoverlapping_edits(self):
        d=self.make('甲乙丙丁戊');d['edits']=[self.op('delete',[0,1],eid='a'),self.op('replace',[3,5],'你',eid='b')]
        self.assertEqual(reconstruct(d)['final'],'乙丙你')
    def test_overlap_rejected(self):
        d=self.make();d['edits']=[self.op('delete',[0,3],eid='a'),self.op('replace',[2,4],'嗯',eid='b')]
        with self.assertRaisesRegex(ManuscriptError,'重叠'):reconstruct(d)
    def test_insert_inside_delete_rejected(self):
        d=self.make();d['edits']=[self.op('delete',[0,3],eid='a'),self.op('insert_after',[1,1],'X',eid='b')]
        with self.assertRaisesRegex(ManuscriptError,'内部'):reconstruct(d)
    def test_insert_at_delete_border(self):
        d=self.make();d['edits']=[self.op('delete',[1,3],eid='a'),self.op('insert_before',[1,1],'Z',eid='b')]
        self.assertEqual(reconstruct(d)['final'],'你Z界')
    def test_unconfirmed_unapplied(self):
        d=self.make();d['edits']=[self.op('delete',[0,2],status='proposed')]
        self.assertEqual(reconstruct(d)['final'],'你好世界')
        self.assertEqual(reconstruct(d)['counts']['pending'],1)
    def test_rejected_unapplied(self):
        d=self.make();d['edits']=[self.op('delete',[0,2],status='rejected')]
        self.assertEqual(reconstruct(d)['counts']['rejected'],1)
    def test_bad_span(self):
        d=self.make();d['edits']=[self.op('delete',[0,50])]
        with self.assertRaises(ManuscriptError):reconstruct(d)
    def test_duplicate(self):
        d=self.make();d['tokens']=[d['tokens'][0],d['tokens'][0]]
        with self.assertRaises(ManuscriptError):reconstruct(d)
    def test_multiple_pages(self):
        a=self.make('第一');b=self.make('第二')
        output=reconstruct_document({'pages':[a,b]})
        self.assertEqual(output['original'],'第一\n\n第二')
    def test_empty(self):
        self.assertEqual(reconstruct(self.make('一')|{'tokens':[]})['original'],'')

if __name__=='__main__':unittest.main()
