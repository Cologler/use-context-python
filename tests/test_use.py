# -*- coding: utf-8 -*-
#
# Copyright (c) 2019~2999 - Cologler <skyoflw@gmail.com>
# ----------
#
# ----------

import use_context
from use_context import use

def test_order():
    # order is about performance
    assert use_context._IRollbackable.all_subclass == [
        use_context._List,
        use_context._DataClass,
        use_context._GenericContainer,
        use_context._State,
        use_context._Slots,
    ]

def test_user_str():
    class A(str):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.value = 2

    a = A()
    with use(a):
        a.value = 3
        assert a.value == 3
    assert a.value == 2

def test_user_str_with_slots():
    class A(str):
        __slots__ = 'value'

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.value = 2

    assert use_context._get_slots_attrs(A) == ['value']

    a = A()
    with use(a):
        a.value = 3
        assert a.value == 3
    assert a.value == 2

def test_use_list():
    ls = [1, 2, 3]
    with use(ls):
        ls.append(5)
        assert ls == [1, 2, 3, 5]
    assert ls == [1, 2, 3]

def test_use_set():
    s = {1, 2}
    with use(s):
        s.add(15)
        assert s == {1, 2, 15}
    assert s == {1, 2}

def test_use_dict():
    d = {1: 2}
    with use(d):
        d[3] = 4
        assert d == {1: 2, 3: 4}
    assert d == {1: 2}

def test_dataclass():
    from dataclasses import dataclass
    @dataclass
    class A:
        f1: str
        f2: str
        f3: str

    a = A('1', '2', '3')
    with use(a):
        a.f1 = '6'
        assert a == A('6', '2', '3')
    assert a == A('1', '2', '3')

def test_state():
    class A:
        def get_state(self):
            return vars(self).copy()

        def from_state(self, state):
            vars(self).clear()
            vars(self).update(state)

    a = A()
    a.a = 1
    with use(a):
        a.a = 2
        assert a.a == 2
    assert a.a == 1

def test_with_dict():
    class A:
        pass

    a = A()
    a.a = 1
    with use(a):
        a.a = 2
        assert a.a == 2
    assert a.a == 1

def test_with_slots():
    class A:
        __slots__ = ('a', 'b')

    a = A()
    a.a = 1
    with use(a):
        a.a = 2
        a.b = 3
        assert a.a == 2
        assert a.b == 3
    assert a.a == 1
    assert not hasattr(a, 'b')
