# use-context

## Usage

``` py
from use_context import use

ls = [1, 2, 3]
with use(ls):
    ls.append(5)
assert ls == [1, 2, 3]
```
