from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from monitor import AutoRetry, Failure, HERE, Journal

class FakeScanner:
    def __init__(self, failures): self.failures = failures
    def scan(self): return self.failures

class AutoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='retry-test-', dir=HERE)
        self.addCleanup(self.tmp.cleanup)
        self.now = [datetime(2026,10,21,15,59,50,tzinfo=timezone.utc).timestamp()]
        self.journal = Journal(Path(self.tmp.name)/'actions.jsonl',clock=lambda:self.now[0], tz=timezone(timedelta(hours=8)))
        self.failure = Failure('chat-a','failed-1','真实目标',1,'服务不可用')
        self.notices, self.calls = [], []
        self.scanner = FakeScanner([self.failure])
        outer = self
        class Sender:
            def send(self, failure):
                outer.calls.append(failure)
                outer.journal.record(failure,'sent','id-'+failure.turn_id)
                return 'sent','ok'
        self.sender = Sender()

    def engine(self, sender=None):
        return AutoRetry(self.scanner,self.journal,sender or self.sender,self.notices.append,clock=lambda:self.now[0])

    def test_auto_send_once_and_notice_uses_confirmed_count(self):
        engine=self.engine()
        engine.tick()
        engine.tick()
        self.assertEqual(self.calls,[self.failure])
        self.assertEqual(self.notices,[{'kind':'sent','count':1,'thread_id':'chat-a','title':'真实目标'}])

    def test_daily_rollover_and_restart_keep_actual_counts(self):
        self.journal.record(self.failure,'sent','one')
        self.journal.record(self.failure,'sent','one')
        self.journal.record(self.failure,'unknown','unknown')
        self.assertEqual(self.journal.daily_count(),1)
        reread=Journal(self.journal.path,clock=lambda:self.now[0],tz=timezone(timedelta(hours=8)))
        self.assertEqual(reread.daily_count(),1)
        self.now[0]+=20  # Hong Kong midnight, while UTC is still Oct 21.
        self.assertEqual(reread.daily_count(),0)
        reread.record(self.failure,'sent','two')
        self.assertEqual(reread.daily_count(),1)

    def test_spacing_between_new_failed_turns_survives_restart(self):
        self.engine().tick()
        self.scanner.failures=[Failure('chat-a','failed-2','same chat',2,'服务不可用')]
        self.journal=Journal(self.journal.path,clock=lambda:self.now[0])
        engine=self.engine()
        self.now[0]+=29
        engine.tick()
        self.assertEqual(len(self.calls),1)
        self.now[0]+=1
        engine.tick()
        self.assertEqual(len(self.calls),2)

    def test_multiple_threads_are_independent(self):
        self.scanner.failures.append(Failure('chat-b','b1','other',1,'服务不可用'))
        self.engine().tick()
        self.assertEqual({f.thread_id for f in self.calls},{'chat-a','chat-b'})
        self.assertEqual([n['count'] for n in self.notices],[1,2])

    def test_unknown_never_increments_or_repeats(self):
        outer=self
        class Unknown:
            def send(self,failure):
                outer.calls.append(failure)
                outer.journal.record(failure,'unknown','u1')
                return 'unknown','unknown'
        engine=self.engine(Unknown())
        engine.tick()
        engine.tick()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.journal.daily_count(),0)
        self.assertEqual(self.notices[0]['kind'],'unknown')

    def test_preflight_failure_backs_off_without_fake_success(self):
        outer=self
        class Unavailable:
            def send(self,failure):
                outer.calls.append(failure)
                return 'error','no desktop'
        engine=self.engine(Unavailable())
        engine.tick()
        engine.tick()
        self.assertEqual(len(self.calls),1)
        self.now[0]+=5
        engine.tick()
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.notices,[])
        self.assertEqual(self.journal.daily_count(),0)

    def test_stop_before_work_never_sends(self):
        engine=self.engine()
        engine.stopped=lambda:True
        engine.tick()
        self.assertEqual(self.calls,[])

    def test_old_dismissal_cannot_unlock_an_already_sent_turn(self):
        self.journal.record(self.failure,'sent','one')
        self.journal.record(self.failure,'dismissed')
        self.journal=Journal(self.journal.path,clock=lambda:self.now[0])
        self.engine().tick()
        self.assertEqual(self.calls,[])

    def test_kitchen_trajectory_is_parabolic_and_toast_is_stationary_for_one_second(self):
        import random
        from kitchen_art import Flight,Toast
        paths=[]
        for seed in (1,2,3):
            route=Flight(0,0,1920,1040,280,280,1,random.Random(seed))
            points=[route.point(i/100) for i in range(101)]
            self.assertTrue(all(a[0]>b[0] for a,b in zip(points,points[1:])))
            self.assertTrue(all(0<y<1040-280 for x,y,a in points))
            self.assertGreater(max(y for x,y,a in points)-min(y for x,y,a in points),100)
            self.assertGreater(points[0][0],1920)
            self.assertLess(points[-1][0],-280)
            acceleration=[c[1]-2*b[1]+a[1] for a,b,c in zip(points,points[1:],points[2:])]
            self.assertGreater(min(acceleration),0)
            self.assertLess(max(acceleration)-min(acceleration),1e-8)
            self.assertEqual(min(range(101),key=lambda i:points[i][1]),50)
            paths.append(points)
        self.assertEqual(len({tuple(path) for path in paths}),3)
        toast=Toast(0,0,1920,1040,370,68,1)
        self.assertEqual(toast.position,(1530,952))
        self.assertTrue(toast.visible(.999))
        self.assertFalse(toast.visible(1))
        self.assertFalse(toast.visible(2))

    def test_kitchen_shuffle_covers_all_items_and_persists_across_restart(self):
        import random
        from kitchen_art import KitchenArt
        state=Path(self.tmp.name)/'order.json'
        art=KitchenArt(1,state,random.Random(5))
        count=len(art.items)
        self.assertEqual(count,28)
        first=[art.choose()['id'] for _ in range(10)]
        resumed=KitchenArt(1,state,random.Random(9))
        first.extend(resumed.choose()['id'] for _ in range(count-10))
        second=[resumed.choose()['id'] for _ in range(count)]
        self.assertEqual(set(first),set(art.by_id))
        self.assertEqual(set(second),set(art.by_id))
        self.assertNotEqual(first[-1],second[0])
        self.assertNotEqual(first,second)

    def test_kitchen_assets_have_transparency_and_fit_when_rotated(self):
        import math
        from kitchen_art import KitchenArt,ASSETS
        from PIL import Image
        art=KitchenArt(1)
        for item in art.items:
            with Image.open(ASSETS/item['file']) as image:
                self.assertEqual(image.size,(640,640))
                self.assertEqual(image.getchannel('A').getextrema(),(0,255))
            art.sprite=art.load(item['id'])
            for angle in (0,math.pi/4,math.pi/2):
                box=art.frame(angle).getbbox()
                self.assertGreater(min(box[:2]),0)
                self.assertLess(max(box[2:]),art.size)

if __name__=='__main__':
    unittest.main(verbosity=2)
