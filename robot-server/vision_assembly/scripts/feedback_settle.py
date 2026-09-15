"""Require distinct, continuous feedback samples; never infer physical grasp."""
class FeedbackSettle:
    def __init__(self, duration=1.0, minimum_samples=5, maximum_gap=.25):
        self.duration=duration;self.minimum_samples=minimum_samples;self.maximum_gap=maximum_gap
        self.first=None;self.last=None;self.sequence=None;self.count=0

    def update(self, sequence, now, valid):
        if sequence==self.sequence:return False
        self.sequence=sequence
        if not valid or (self.last is not None and now-self.last>self.maximum_gap):
            self.first=None;self.count=0
        self.last=now
        if not valid:return False
        if self.first is None:self.first=now
        self.count+=1
        return self.count>=self.minimum_samples and now-self.first>=self.duration
