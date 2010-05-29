import datetime

from stdnet.main import get_cache
from stdnet.utils import json

from jflow.conf import settings
from jflow.core.dates import date2yyyymmdd

__all__ = ['cache','FinInsBase','Portfolio','FinIns','Position']

cache = get_cache(settings.PORTFOLIO_CACHE_BACKEND or settings.CACHE_BACKEND)


class FinInsBase(object):
    notavailable  = '#N/A'
    
    def __init__(self, id = None, name = None, description = None, dt = None, ccy = None):
        self.id = id
        self.name = name or ''
        self.description = description or ''
        self.ccy = ccy
        
    def __repr__(self):
        return '%s:%s' % (self.name,self.dt)
    
    def __str__(self):
        return self.__repr__()
    
    def has_id(self, id):
        return False
    
    def prekey(self):
        return '%s:%s' % (self.__class__.__name__.lower(),date2yyyymmdd(self.dt))
        
    def key(self):
        return '%s:#%s' % (self.prekey(),self.id)
    
    def namekey(self):
        return '%s:$%s' % (self.prekey(),self.name)
    
    def tojson(self):
        return json.dumps(self.__dict__)
    

class FinDated(FinInsBase):
    
    def __init__(self, dt = None, **kwargs):
        self.dt = dt or datetime.date.today()
        super(FinDated,self).__init__(**kwargs)


class Portfolio(FinDated):
    '''A portfolio containing positions and portfolios'''
    
    def get(self, id, default = None):
        code = '%s:position:$%s' % (self.key(),id)
        return cache.get(code.lower(),default)
    
    def setkey(self):
        return '%s:positions' % self.namekey()
    
    def positions(self):
        '''Portfolio positions'''
        positions = cache.sinter(self.setkey())
        for position in positions:
            yield cache.get(position)
            
    def add(self, item):
        if isinstance(item,PositionBase):
            cal
            if self.has_key(c):
                raise KeyError, '%s already available in %s' % (c,self)
            else:
                self._positions[c] = item
                return item
        else:
            return None
    
    def get_portfolio(self):
        pos = []
        for v in self._positions.itervalues():
            pos.append(v.dict())
        return pos
    
    
class FinIns(FinInsBase):
    '''Financial instrument base class                
    '''    
    def __init__(self, multiplier = 1.0, **kwargs):
        self.multiplier    = multiplier
        super(FinIns,self).__init__(**kwargs)
        
    def pv01(self):
        '''Present value of a basis point. This is a Fixed Income notation which we try to extrapolate to
        all financial instruments'''
        return 0
 
 
class Position(FinDated):
    '''Financial position::
    
        * *sid* security id or None. For securities this is the underlying financial instrument id.
        * *size* size of position
        * *value* initial value of position
        * *dt* position date
    '''
    def __init__(self, sid = None, size = 1, value = 0, **kwargs):
        self.sid    = sid
        self.size   = size
        self.value  = value
        super(Position,self).__init__(**kwargs)

    def security(self):
        if self.sid:
            return cache.get(self.sid)