# jinjax

`shared.jinjax` is a thin, self-contained layer over
[Jinja2](https://jinja.palletsprojects.com/) with Carmilla's own extensions
(currently: an extended `tojson` filter).

The goal is a single shared Jinja environment for the whole application —
instead of creating bare `jinja2.Template(...)` instances in many places, you
import from `shared.jinjax` and get a guarantee that all filters/policies are
configured consistently.

## Usage

Drop-in replacement for `from jinja2 import Template`:

```python
from shared.jinjax import Template

t = Template("Hello {{ name }}!")
print(t.render(name="Carmilla"))
```

The public API is intentionally tiny:

```python
from shared.jinjax import (
    Template,    # jinja2.Template replacement (source: str only)
    env,         # shared, loaderless jinja2.Environment (string templates)
    create_env,  # factory for a new environment with the same extensions
)
```

`env` and any environment from `create_env(...)` are plain `jinja2.Environment`
instances — use their native methods directly instead of bespoke wrappers:

```python
from shared.jinjax import env

env.from_string("Hello {{ name }}").render(name="Carmilla")
```

### Name-based templates (loaders)

The shared `env` has no loader, so it only renders string templates. For
name-based templates build your own environment — `create_env(...)` forwards
all arguments to `jinja2.Environment(...)`:

```python
from jinja2 import FileSystemLoader
from shared.jinjax import create_env

tpl_env = create_env(loader=FileSystemLoader("templates"))
html = tpl_env.get_template("page.html").render(title="Hi")
```

The custom filters are registered on every environment `create_env` returns.

### `tojson` filter

An extended version of the standard `tojson` filter. Unlike Jinja's built-in,
it targets Markdown output: by default it produces **raw, unescaped JSON** with
`ensure_ascii=False`, so non-ASCII characters (e.g. Polish letters, emoji) are
emitted as-is and `<`, `>`, `&`, `'` are *not* escaped.

Parameters:

| param          | default | effect                                            |
| -------------- | ------- | ------------------------------------------------- |
| `indent`       | `None`  | pretty-print indentation (compact when `None`)    |
| `ensure_ascii` | `False` | escape non-ASCII as `\uXXXX`                       |
| `html_safe`    | `False` | escape `<`, `>`, `&`, `'` and wrap in `Markup`     |
| `sort_keys`    | `False` | sort object keys alphabetically                   |

```jinja
{{ obj | tojson }}                {# raw JSON, ensure_ascii=False #}
{{ obj | tojson(2) }}             {# indent=2 #}
{{ obj | tojson(None, True) }}    {# ensure_ascii=True #}
{{ obj | tojson(html_safe=True) }}{# HTML-safe (escapes <, >, &, ') #}
{{ obj | tojson(sort_keys=True) }}{# keys sorted alphabetically #}
```

> **Security note:** when embedding the output inside an HTML `<script>` block,
> pass `html_safe=True` **and** `ensure_ascii=True`. `html_safe` does not escape
> the U+2028/U+2029 line/paragraph separators, which Jinja sidesteps via
> `ensure_ascii=True`; with `ensure_ascii=False` those are emitted raw and can
> break or inject JavaScript.

## Structure

```
jinjax/
├── __init__.py       # public API (re-export)
├── api.py            # Template (drop-in replacement)
├── environment.py    # create_env(...) + shared `env` singleton
├── filters/
│   ├── __init__.py   # register_filters(env) — registers all filters
│   └── tojson.py     # tojson filter
└── README.md
```

All environment-configuring code (policies, filter registration) lives in
[environment.py](environment.py). The public functions are in [api.py](api.py)
and should not contain configuration logic.

## Extending

### Adding a new filter

1. Create a module under `filters/`, e.g. `filters/slugify.py`, with the filter
   function.
2. Import it in [filters/__init__.py](filters/__init__.py) and add an entry to
   `register_filters()`:

   ```python
   from .slugify import slugify

   def register_filters(env):
       env.filters["tojson"] = tojson
       env.filters["slugify"] = slugify
   ```

### Globals, tests, Jinja extensions

Similarly: add `register_globals(env)` / `register_tests(env)` /
`register_extensions(env)` (e.g. in separate modules) and call them from
`create_env()` alongside `register_filters(env)`.

## Using outside this project

`shared.jinjax` has no dependencies on the rest of Carmilla — it only depends
on `jinja2`.

```
pip install jinja2
```

Copy the `shared/jinjax` directory and make it importable as `shared.jinjax`
(add its parent directory to `PYTHONPATH` or install it as a local package).
If the `shared` name clashes, change the import path — the code uses only
relative imports inside the package, so moving the directory is enough.
