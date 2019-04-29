# use-context

![GitHub](https://img.shields.io/github/license/Cologler/use-context-python.svg)
[![Build Status](https://travis-ci.com/Cologler/use-context-python.svg?branch=master)](https://travis-ci.com/Cologler/use-context-python)
[![PyPI](https://img.shields.io/pypi/v/use-context.svg)](https://pypi.org/project/use-context/)

use some vars in current context and try rollback state when exit the context.

## Usage

By default:

``` py
from use_context import use

ls = [1, 2, 3]
with use(ls):
    ls.append(5)
assert ls == [1, 2, 3]
```

For use ref (by name):

``` py
a = 15
with use(refs=['a']) as ctx:
    assert not ctx.is_ref_changed('a')
    a = 16
    assert a == 16
    assert ctx.is_ref_changed('a')
assert a == 15
```

👍
