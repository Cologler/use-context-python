# use-context

![GitHub](https://img.shields.io/github/license/Cologler/use-context-python.svg)
[![Build Status](https://travis-ci.com/Cologler/use-context-python.svg?branch=master)](https://travis-ci.com/Cologler/use-context-python)
[![PyPI](https://img.shields.io/pypi/v/use-context.svg)](https://pypi.org/project/use-context/)

use some vars in current context and try rollback state when exit the context.

## Usage

``` py
from use_context import use

ls = [1, 2, 3]
with use(ls):
    ls.append(5)
assert ls == [1, 2, 3]
```
