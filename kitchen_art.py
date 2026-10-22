"""Generated cartoon kitchen sprites; deterministic physics, shuffled objects."""
import json
import math
from pathlib import Path
import random
from PIL import Image

ASSETS=Path(__file__).resolve().parent/'assets'/'kitchen'


class KitchenArt:
    size=280

    def __init__(self,scale,state_path=None,rng=None):
        self.scale=scale
        self.rng=rng or random.SystemRandom()
        self.state_path=state_path
        self.items=json.loads((ASSETS/'manifest.json').read_text(encoding='utf-8'))
        self.by_id={item['id']:item for item in self.items}
        self.remaining=[]
        self.last=None
        if state_path and state_path.exists():
            try:
                state=json.loads(state_path.read_text(encoding='utf-8'))
                remaining=state['remaining']
                if (len(remaining)==len(set(remaining)) and all(x in self.by_id for x in remaining)
                        and state.get('last') in self.by_id):
                    self.remaining=remaining
                    self.last=state['last']
            except (ValueError,KeyError,TypeError):
                pass
        self.sprite=None

    def choose(self):
        if not self.remaining:
            self.remaining=list(self.by_id)
            self.rng.shuffle(self.remaining)
            if self.remaining[-1]==self.last:
                self.remaining[0],self.remaining[-1]=self.remaining[-1],self.remaining[0]
        self.last=self.remaining.pop()
        if self.state_path:
            temp=self.state_path.with_suffix('.tmp')
            temp.write_text(json.dumps({'remaining':self.remaining,'last':self.last}),encoding='utf-8')
            temp.replace(self.state_path)
        self.sprite=self.load(self.last)
        return self.by_id[self.last]

    def load(self,item_id):
        with Image.open(ASSETS/self.by_id[item_id]['file']) as image:
            image=image.convert('RGBA')
            box=image.getbbox()
            if not box:
                raise ValueError('Empty kitchen sprite: '+item_id)
            image=image.crop(box)
        # Bound the diagonal so the handle stays intact at every rotation.
        factor=240*self.scale/math.hypot(*image.size)
        image=image.resize((max(1,round(image.width*factor)),max(1,round(image.height*factor))),Image.Resampling.LANCZOS)
        sprite=Image.new('RGBA',(round(self.size*self.scale),)*2)
        sprite.alpha_composite(image,((sprite.width-image.width)//2,(sprite.height-image.height)//2))
        return sprite

    def frame(self,angle):
        return self.sprite.rotate(-math.degrees(angle),resample=Image.Resampling.BICUBIC)


class Flight:
    """Constant horizontal velocity and constant downward acceleration."""
    def __init__(self,left,top,right,bottom,width,height,scale,rng=None):
        rng=rng or random.SystemRandom()
        self.start,self.end=right+8,left-width-8
        low=top+12*scale
        available=max(0,bottom-height-30*scale-low)
        self.baseline=low+available*rng.uniform(.80,.96)
        self.lift=max(0,self.baseline-low)*rng.uniform(.72,.94)
        self.angle=rng.uniform(-.4,.4)
        self.spin=rng.choice((-1,1))*rng.uniform(.8,1.6)*math.tau

    def point(self,p):
        p=max(0,min(1,p))
        return (self.start+(self.end-self.start)*p,
                self.baseline-4*self.lift*p*(1-p),
                self.angle+self.spin*p)


class Toast:
    duration=1.0

    def __init__(self,left,top,right,bottom,width,height,scale):
        self.position=(max(left,right-width-20*scale),max(top,bottom-height-20*scale))

    def visible(self,elapsed):
        return 0<=elapsed<self.duration
