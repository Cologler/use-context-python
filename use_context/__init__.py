# -*- coding: utf-8 -*-
#
# Copyright (c) 2019~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import abc
import collections
import dataclasses
import decimal
import inspect
import ctypes


_Immutable = frozenset([
    bool,
    int, float, complex, decimal.Decimal,
    str,
    tuple,
    frozenset
])


class _IRollbackable(abc.ABC):
    type_map = {}
    all_subclass = []

    __slots__ = ('target', 'state')

    def __init__(self, target):
        self.target = target
        self.state = None

    @abc.abstractmethod
    def get_state(self):
        '''
        get current state from target
        '''
        raise NotImplementedError

    def track(self):
        '''
        begin track the target
        '''
        self.state = self.get_state()

    def is_changed(self):
        '''
        check whether the state of target is changed or not
        '''
        return self.state != self.get_state()

    @abc.abstractmethod
    def rollback(self):
        '''
        rollback state of target from when it being track
        '''
        raise NotImplementedError

    def __init_subclass__(cls):
        _IRollbackable.all_subclass.append(cls)
        for tp in vars(cls).get('types', ()):
            _IRollbackable.type_map[tp] = cls

    @staticmethod
    def has_proto(target):
        return False


class _List(_IRollbackable):
    __slots__ = ()
    types = (list, )

    def get_state(self):
        return self.target.copy()

    def rollback(self):
        self.target[:] = self.state


class _DataClass(_IRollbackable):
    __slots__ = ()

    def get_state(self):
        state = {}
        for f in dataclasses.fields(self.target):
            try:
                # dataclass cannot delete attr
                # which make dataclass raise error when it use equal op
                # however I catch it here.
                state[f.name] = getattr(self.target, f.name)
            except AttributeError:
                pass
        return state

    def rollback(self):
        for f in dataclasses.fields(self.target):
            if f.name in self.state:
                setattr(self.target, f.name, self.state[f.name])

            # a great dataclass should never get there:
            elif hasattr(self.target, f.name):
                delattr(self.target, f.name)

    @staticmethod
    def has_proto(target):
        return dataclasses.is_dataclass(target)


class _GenericContainer(_IRollbackable):
    __slots__ = ()
    types = (
        set, dict, collections.defaultdict
    )

    def get_state(self):
        return self.target.copy()

    def rollback(self):
        self.target.clear()
        self.target.update(self.state)

    @staticmethod
    def has_proto(target):
        for name in ('copy', 'clear', 'update'):
            if not callable(getattr(target, name, None)):
                return False
        return True


class _State(_IRollbackable):
    __slots__ = ()

    def get_state(self):
        return self.target.get_state()

    def rollback(self):
        self.target.from_state(self.state)

    @staticmethod
    def has_proto(target):
        for name in ('get_state', 'from_state'):
            if not callable(getattr(target, name, None)):
                return False
        return True


class _Slots(_IRollbackable):
    __slots__ = ('attrs')

    def __init__(self, target, attrs):
        super().__init__(target)
        self.attrs = attrs

    def get_state(self):
        state = {}
        for attr in self.attrs:
            try:
                state[attr] = getattr(self.target, attr)
            except AttributeError:
                pass
        return state

    def rollback(self):
        for attr in self.attrs:
            if attr in self.state:
                setattr(self.target, attr, self.state[attr])
            elif hasattr(self.target, attr):
                delattr(self.target, attr)


class _RollbackableProxy(_IRollbackable):
    __slots__ = ('proxy_obj')

    def __init__(self, target, proxy_for: _IRollbackable):
        super().__init__(target)
        self.proxy_obj = proxy_for

    def get_state(self):
        return self.proxy_obj.get_state()

    def track(self):
        return self.proxy_obj.track()

    def is_changed(self):
        return self.proxy_obj.is_changed()

    def rollback(self):
        return self.proxy_obj.rollback()


class _Ref:
    __slots__ = ('frame', 'name', 'state', 'in_local')

    def __init__(self, frame, name):
        self.frame = frame
        self.name = name
        self.in_local = name in (self.frame.f_code.co_varnames + self.frame.f_code.co_freevars)
        self.state = self._d()[self.name]

    def _d(self):
        if self.in_local:
            return self.frame.f_locals
        else:
            return self.frame.f_globals

    def is_changed(self):
        return self._d()[self.name] is not self.state

    def rollback(self):
        self._d()[self.name] = self.state
        # update f_locals
        # https://www.python.org/dev/peps/pep-0558/
        if self.in_local:
            ctypes.pythonapi.PyFrame_LocalsToFast(
                ctypes.py_object(self.frame),
                ctypes.c_int(0)
            )


def _get_slots_attrs(cls):
    attrs = set()
    for base in cls.__mro__:
        s = getattr(base, '__slots__', ())
        if isinstance(s, str):
            s = (s, ) # __slots__ == 'abc' equals __slots__ == ('abc', )
        attrs.update(s)
    return list(attrs)


class _Context:
    __slots__ = ('_tracked', '_ref_tracked')

    def __init__(self):
        self._tracked = []
        self._ref_tracked = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.rollback()

    def _begin_track(self, rb: _IRollbackable):
        rb.track()
        self._tracked.append(rb)

    def track_ref(self, name):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        frame = calframe[2].frame
        self._ref_tracked.append(_Ref(frame, name))

    def track(self, item):
        cls = type(item)

        if cls in _Immutable:
            raise TypeError(f'{cls!r} is immutable')

        rb_cls = _IRollbackable.type_map.get(cls)

        if rb_cls is not None:
            return self._begin_track(rb_cls(item))

        for prbcls in _IRollbackable.all_subclass:
            if prbcls.has_proto(item):
                return self._begin_track(prbcls(item))

        # object with __dict__

        try:
            d = vars(item)
        except TypeError:
            d = None

        if isinstance(d, dict):
            return self._begin_track(_RollbackableProxy(item, _GenericContainer(d)))

        if d is None:
            # object with __slots__
            attrs = _get_slots_attrs(cls)
            return self._begin_track(_Slots(item, attrs))

        raise TypeError(f'unknown type: {cls!r}')

    def rollback(self):
        while self._tracked:
            self._tracked.pop().rollback()
        while self._ref_tracked:
            self._ref_tracked.pop().rollback()

    def is_changed(self, item):
        '''check whether target is changed or not'''
        for rb in self._tracked:
            if rb.target is item:
                return rb.is_changed()
        raise ValueError(f'untracked object {item!r}')

    def is_ref_changed(self, name: str):
        '''check whether target is changed or not'''
        for ref in self._ref_tracked:
            if ref.name == name:
                return ref.is_changed()
        raise ValueError(f'untracked ref {name!r}')


def use(*items, refs: list=()):
    '''
    use some vars in current context.

    try rollback state when exit the context.
    '''
    ctx = _Context()
    for item in items:
        ctx.track(item)
    for ref_name in refs:
        ctx.track_ref(ref_name)
    return ctx
