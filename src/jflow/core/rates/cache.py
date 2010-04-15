from datetime import datetime

from jflow.conf import settings
from jflow.core import dates
from jflow.core.cache import cache as jflow_cache

__all__ = ['get_cache']

def TrimCodeDefault(code):
    return str(code).upper().replace(' ','_')
    

class rateCache(object):
    '''
    Rate Cache wrapper.
    This object should be used as a singleton.
    It provides an interface to the backend cache to store timeseries
    '''
    def __init__(self, trimcode = None):
        '''
            vendorHandle  object for handling live data feeds from vendors
            gey_currency  function for retriving currency objects
            trimCode      function for trimming data IDs
        '''
        self.cache         = jflow_cache
        self.__timestart   = datetime.now()
        self.factory       = None
        self.loaderpool    = None
        self.vendorHandle  = None
        self.gey_currency  = None
        self.get_field     = None
        self.get_vendor    = None
        self.log_verbose   = settings.LOGGING_VERBOSE
        self.logger        = None
        self.livecalc      = settings.LIVE_CALCULATION
        self.trimCode      = trimcode or TrimCodeDefault
        self.__rates       = {}
        if settings.MAX_RATE_LOADING_THREADS > 0:
            from jflow.utils.tx import ThreadPool
            self.loaderpool = ThreadPool(name = "Rate loader pool",
                                         minthreads = 1,
                                         maxthreads = settings.MAX_RATE_LOADING_THREADS)            
        
    def ratekey(self, key):
        return 'jflow-rate-cache:%s' % key
    
    def get(self, key, dte = None, default = None):
        '''
        Fetch a rate history object if available
        '''
        key = self.trimCode(key)
        rate = self.cache.get(self.ratekey(key),default)
        if dte:
            if rate:
                return rate.get(dte,default)
            else:
                return default
        else:
            return rate
        #return self.__rates.get(ckey,None)
    
    def get_livedate(self, dte):
        dte = dates.get_livedate(dte)
        if not self.livecalc and dte.live:
            return dates.get_livedate(dates.prevbizday())
        else:
            return dte            
    
    def clearlive(self, live_key):
        for r in self.__rates.values():
            r.clearlive(live_key)
            
    def flush(self):
        '''
        Close all connections and flush the memory
        '''
        now = datetime.now()
        mc  = self.minutecache
        nr  = {}
        for k,r in self.__rates.items():
            delta = now - r.lastaccess
            if delta.minutes >= mc:
                r.flush()
            else:
                nr[k] = r
        self.__rates = nr
    
    def clear(self):
        '''
        Close all connections and flush the memory
        '''
        for r in self.__rates:
            r.flush()
        self.__rates = {}
    
    def __set(self, code, creator):
        ts = rateHistory(code,creator)
        self.cache.set(self.ratekey(code),ts)
        #self.__rates[code] = ts
        return ts
    
    def get_rate_holder(self, code):
        if code == None:
            return None
        code  = self.trimCode(code)
        rates = self.get(code)
        if rates == None:
            factory = self.factory
            if factory == None:
                raise ValueError, "Rate factory not available"
            creator = factory.select(code)
            if creator:
                rates = self.__set(code, creator)
        return rates
    
    def log(self, msg, obj = None, verbose = 3):
        if self.logger and verbose <= self.log_verbose:
            obj = obj or self
            msg = '%s - %s' % (obj,msg)
            self.logger.msg(msg)
    
    def err(self, msg, obj = None):
        obj  = obj or self
        msgt = '%s - %s' % (obj,msg)
        if isinstance(msg,Exception):
            msg = msg.__class__(msgt)
        else:
            msg = msgt
        self.logger.err(msg)
            
    def __get_timestart(self):
        return self.__timestart
    timestart = property(fget = __get_timestart)
                

       
def get_cache():
    global _rateCache
    if _rateCache == None:
        _rateCache = rateCache()
    return _rateCache

def trimCode(code):
    cache = get_cache()
    return cache.trimCode(code)


_rateCache = None



class cacheObject(object):
    '''
    Base class for all cache objects
    '''
    def __new__(cls, *args, **kwargs):
        obj = super(cacheObject,cls).__new__(cls)
        obj._cache = get_cache()
        obj.beckend = jflow_cache
        return obj
        
    def __repr__(self):
        return self.__class__.__name__
    
    def __str__(self):
        return self.__repr__()
    
    def __getstate__(self):
        odict = self.__dict__.copy()
        odict.pop('_cache')
        return odict
    
    def __setstate__(self,dict):
        self.__dict__.update(dict)
        self._cache = get_cache()
        self.beckend = jflow_cache
    
    def __get_cache(self):
        return self._cache
    cache = property(fget = __get_cache)
    
    def log(self, msg, obj = None, verbose = 0):
        obj = obj or self
        self.cache.log(msg, obj, verbose = verbose)
        
    def err(self, msg, obj = None):
        obj = obj or self
        self.cache.err(msg, obj)


class rateHistory(cacheObject):
    '''
    Object used to hold in memory an historical time-serie
    '''
    def __init__(self, code, creator):
        '''
        code       rate ascii code
        creator    The rate factory object
        '''
        self._code           = code
        self._factory        = creator
        self._factory.holder = self
        self.live            = None
        
    def __repr__(self):
        return '%s: %s' % (self.__class__.__name__,self._factory)
        
    def __setstate__(self,dict):
        super(rateHistory,self).__setstate__(dict)
        self._factory.holder = self
                
    def flush(self):
        '''
        Flush the memory cache
        '''
        self.__vendors        = {}
        self.live             = None
        
    def empty(self):
        return not (len(self.__vendors) or self.life) 
        
    def timeseries(self, vfid):
        '''
        in-memory time-series for vendor field 'vfid'
        
        @param vfid: vendor field id
        @see: jflow.core.rates.factory.factory.vendorfieldid 
        '''
        vendor = str(vfid.vendor)
        field  = str(vfid.field)
        self.__lastaccess = datetime.now()
        nts = None
        tss = self.__vendors.get(vendor,None)
            
        if tss == None:
            tss = {}
            self.__vendors[vendor] = tss
        else:
            nts = tss.get(field,None)
                
        if nts == None:
            name = str(vfid.code())
            if vfid.numeric:
                nts = numericts(name)
            else:
                nts = dateseries(name)
            
            tss[field] = nts
                
        return nts
    
        
    def clearlive(self, live_key):
        if self.live:
            self.live.clearlive(live_key)
    
    def __get_code(self):
        return self._code
    code = property(fget = __get_code)
        
    def get(self, dte = None):
        dte = get_livedate(dte)
        if dte.live:
            return self.live
        else:
            try:
                return self.ts[dte.date]
            except:
                return None
    
    def add(self, r):
        if not isinstance(r, Rate):
            raise TypeError, '%r is not a Rate object' % r
        if r.live and self.live == None:
            self.live = r
        else:
            dte = r.date
            if not self.ts.has_key(dte):
                self.ts[dte] = r
    
    def get_or_make(self, dte, field = None, vendor = None):
        '''
        get a rate at date dte. If the rate is not available
        it creates it using the factory class
        '''
        dte    = get_livedate(dte)         
        rate   = self.get(dte)
        if rate != None:
            return rate
        # Rate not available, use factory to create one
        creator = self.factory
        if dte.live:
            rate = creator.make(dte)
            if rate != None:
                self.add(rate)
                rate.get(field,vendor)
        else:
            # historical rate
            return self.get_history(dte, dte, field = field, vendor = vendor)
        return rate
    
    def get_history(self,
                    start  = None,
                    end    = None,
                    field  = None,
                    vendor = None,
                    period = 'd',
                    parent = None):
        '''
        Call the factory class to load the history
        '''
        return self.factory.loadhistory(start,end,field,vendor,period=period,parent=parent)
    
    def register_to_rates(self, start=None, end=None, field=None, observer = None):
        '''
        Register an observer to a given rate
        '''
        start = get_livedate(start)
        end   = get_livedate(end)
        if start >= end:
            end = start
        if end.live:
            r = self.get_or_make(end,field)
            r.attach(observer)
        if start < end:
            return self.factory.loadhistory(start,end,field,observer=observer)
    
    def __get_factory(self):
        return self._factory
    factory = property(fget = __get_factory)
    
    def __get_loaderpool(self):
        return self.cache.loaderpool
    loaderpool = property(fget = __get_loaderpool)
    
    def getts(self, start, end, vfid):
        ts    = self.timeseries(vfid)
        return ts.copy(start.date,end.date)
        #for d,v in ts.items():
        #    if d >= start:
        #        if d>end:
        #            break
        #        nv = v.get(field = field, vendor = vendor)
        #        if nv:
        #            ts[d] = nv
        #if liv and self.live:
        #    nv = self.live.get(field = field, vendor = vendor)
        #    if nv:
        #        ts[end] = nv
        #        
        #return ts
    
    def register_observer(self, start, end, field, observer):
        start = toboostdate(start.date)
        if end.live:
            end = dates.today()
        else:
            end   = toboostdate(end.date)
        for d,v in self.ts.items():
            if d >= start:
                if d>end:
                    break
                v.attach(observer)

    def start(self):
        key = '%s:start' % self.cache.ratekey(self.code)
        return self.backend.get(key)

    def end(self):
        key = '%s:end' % self.cache.ratekey(self.code)
        return self.backend.get(key)
    
        

