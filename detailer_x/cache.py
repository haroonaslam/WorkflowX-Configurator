"""Bounded CPU-only stage cache; snapshots are never shared mutably with callers."""
from collections import OrderedDict
import hashlib
import json
import threading
import uuid
import weakref
import types
import functools

class StageCache:
    def __init__(self, limit=2*1024**3):
        self.limit, self.bytes = limit, 0
        self.items = OrderedDict()
        self.lock = threading.RLock()

    def get(self, key):
        with self.lock:
            if key not in self.items:
                return None
            self.items.move_to_end(key)
            return _clone(self.items[key])

    def put(self, key, image):
        size = _size(image)
        if size > self.limit:
            return
        with self.lock:
            old=self.items.pop(key,None)
            if old is not None:
                self.bytes-=_size(old)
            while self.items and self.bytes+size>self.limit:
                _,old=self.items.popitem(last=False)
                self.bytes-=_size(old)
            self.items[key]=_clone(image)
            self.bytes+=size

    def clear(self):
        with self.lock:
            self.items.clear()
            self.bytes=0

CACHE=StageCache()

def _clone(value):
    import torch
    if isinstance(value,torch.Tensor):return value.detach().cpu().clone()
    if isinstance(value,dict):return {k:_clone(v) for k,v in value.items()}
    if isinstance(value,list):return [_clone(v) for v in value]
    if isinstance(value,tuple):return tuple(_clone(v) for v in value)
    return value

def _size(value):
    import torch
    if isinstance(value,torch.Tensor):return value.numel()*value.element_size()
    if isinstance(value,dict):return sum(_size(v) for v in value.values())
    if isinstance(value,(list,tuple)):return sum(_size(v) for v in value)
    return 0
_identities=weakref.WeakKeyDictionary()
_identity_lock=threading.RLock()

def identity(value):
    with _identity_lock:
        try:
            if value not in _identities:
                _identities[value]=uuid.uuid4().hex
            return _identities[value]
        except TypeError:
            # Unknown/non-weak-referenceable mutable object: deliberately miss.
            return uuid.uuid4().hex

def fingerprint(value, depth=0):
    import torch
    if depth>12:
        return uuid.uuid4().hex
    if isinstance(value,torch.Tensor):
        raw=value.detach().cpu().contiguous()
        return (str(raw.dtype),tuple(raw.shape),hashlib.sha256(raw.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest())
    if value is None or type(value) in (str,int,float,bool):
        return value
    if isinstance(value,(list,tuple)):
        return [fingerprint(v,depth+1) for v in value]
    if isinstance(value,dict):
        return {str(k):fingerprint(v,depth+1) for k,v in value.items()}
    if isinstance(value, functools.partial):
        return [fingerprint(value.func,depth+1),fingerprint(value.args,depth+1),fingerprint(value.keywords,depth+1)]
    if isinstance(value, types.FunctionType):
        # Functions used by attention patches are immutable code plus closures.
        # Fingerprint closure values so a captured mutable setting invalidates.
        return [identity(value),hashlib.sha256(value.__code__.co_code).hexdigest(),
                fingerprint(value.__defaults__,depth+1),fingerprint(value.__kwdefaults__,depth+1),
                [fingerprint(c.cell_contents,depth+1) for c in (value.__closure__ or ())],
                fingerprint(value.__dict__,depth+1)]
    if isinstance(value, (torch.dtype,torch.device)):
        return str(value)
    if callable(value):
        # Callable closures can carry mutable state that cannot be inspected safely.
        return uuid.uuid4().hex
    return uuid.uuid4().hex

def model_signature(model, clip, vae):
    # ModelPatcher assigns a new patches_uuid when patches change. Options hold
    # attention and sampling patches; unknown option objects invalidate safely.
    result=[]
    for obj in (model,getattr(clip,"patcher",clip),getattr(vae,"patcher",vae)):
        patch_id=getattr(obj,"patches_uuid",None)
        if patch_id is None:
            result.append(uuid.uuid4().hex)
        else:
            result.append((identity(obj),str(patch_id),fingerprint(getattr(obj,"model_options",{})),
                           fingerprint(getattr(obj,"object_patches",{}))))
    return result

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(",",":")).encode()).hexdigest()
