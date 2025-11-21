# mypy: allow-untyped-defs
import ast
from bisect import bisect_right
from functools import lru_cache
import inspect
import textwrap
import tokenize
import types
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import overload
from typing import Tuple
from typing import Union
import warnings


class Source:
    """An immutable object holding a source code fragment.

    When using Source(...), the source lines are deindented.
    """

    def __init__(self, obj: object = None) -> None:
        if not obj:
            self.lines: List[str] = []
        elif isinstance(obj, Source):
            self.lines = obj.lines
        elif isinstance(obj, (tuple, list)):
            self.lines = deindent(x.rstrip("\n") for x in obj)
        elif isinstance(obj, str):
            self.lines = deindent(obj.split("\n"))
        else:
            try:
                rawcode = getrawcode(obj)
                src = inspect.getsource(rawcode)
            except TypeError:
                src = inspect.getsource(obj)  # type: ignore[arg-type]
            self.lines = deindent(src.split("\n"))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Source):
            return NotImplemented
        return self.lines == other.lines

    # Ignore type because of https://github.com/python/mypy/issues/4266.
    __hash__ = None  # type: ignore

    @overload
    def __getitem__(self, key: int) -> str: ...

    @overload
    def __getitem__(self, key: slice) -> "Source": ...

    def __getitem__(self, key: Union[int, slice]) -> Union[str, "Source"]:
        if isinstance(key, int):
            return self.lines[key]
        else:
            if key.step not in (None, 1):
                raise IndexError("cannot slice a Source with a step")
            newsource = Source()
            newsource.lines = self.lines[key.start : key.stop]
            return newsource

    def __iter__(self) -> Iterator[str]:
        return iter(self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    def strip(self) -> "Source":
        """Return new Source object with trailing and leading blank lines removed."""
        start, end = 0, len(self)
        while start < end and not self.lines[start].strip():
            start += 1
        while end > start and not self.lines[end - 1].strip():
            end -= 1
        source = Source()
        source.lines[:] = self.lines[start:end]
        return source

    def indent(self, indent: str = " " * 4) -> "Source":
        """Return a copy of the source object with all lines indented by the
        given indent-string."""
        newsource = Source()
        newsource.lines = [(indent + line) for line in self.lines]
        return newsource

    def getstatement(self, lineno: int) -> "Source":
        """Return Source statement which contains the given linenumber
        (counted from 0)."""
        start, end = self.getstatementrange(lineno)
        return self[start:end]

    def getstatementrange(self, lineno: int) -> Tuple[int, int]:
        """Return (start, end) tuple which spans the minimal statement region
        which containing the given lineno."""
        if not (0 <= lineno < len(self)):
            raise IndexError("lineno out of range")
        ast, start, end = getstatementrange_ast(lineno, self)
        return start, end

    def deindent(self) -> "Source":
        """Return a new Source object deindented."""
        newsource = Source()
        newsource.lines[:] = deindent(self.lines)
        return newsource

    def __str__(self) -> str:
        return "\n".join(self.lines)


#
# helper functions
#


def findsource(obj) -> Tuple[Optional[Source], int]:
    try:
        sourcelines, lineno = inspect.findsource(obj)
    except Exception:
        return None, -1
    source = Source()
    source.lines = [line.rstrip() for line in sourcelines]
    return source, lineno


def getrawcode(obj: object, trycall: bool = True) -> types.CodeType:
    """Return code object for given function."""
    try:
        return obj.__code__  # type: ignore[attr-defined,no-any-return]
    except AttributeError:
        pass
    if trycall:
        call = getattr(obj, "__call__", None)
        if call and not isinstance(obj, type):
            return getrawcode(call, trycall=False)
    raise TypeError(f"could not get code object for {obj!r}")


def deindent(lines: Iterable[str]) -> List[str]:
    return textwrap.dedent("\n".join(lines)).splitlines()


def get_statement_startend2(lineno: int, node: ast.AST) -> Tuple[int, Optional[int]]:
    # Flatten all statements and except handlers into one lineno-list.
    # AST's line numbers start indexing at 1.
    values: List[int] = []
    for x in ast.walk(node):
        if isinstance(x, (ast.stmt, ast.ExceptHandler)):
            # The lineno points to the class/def, so need to include the decorators.
            if isinstance(x, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in x.decorator_list:
                    values.append(d.lineno - 1)
            values.append(x.lineno - 1)
            for name in ("finalbody", "orelse"):
                val: Optional[List[ast.stmt]] = getattr(x, name, None)
                if val:
                    # Treat the finally/orelse part as its own statement.
                    values.append(val[0].lineno - 1 - 1)
    values.sort()
    insert_index = bisect_right(values, lineno)
    start = values[insert_index - 1]
    if insert_index >= len(values):
        end = None
    else:
        end = values[insert_index]
    return start, end


def getstatementrange_ast(
    lineno: int,
    source: Source,
    assertion: bool = False,
    astnode: Optional[ast.AST] = None,
) -> Tuple[ast.AST, int, int]:
    if astnode is None:
        content = str(source)
        astnode = _parse_ast_from_source(content)

    start, end = get_statement_startend2(lineno, astnode)
    # We need to correct the end:
    # - ast-parsing strips comments
    # - there might be empty lines
    # - we might have lesser indented code blocks at the end
    if end is None:
        end = len(source.lines)

    if end > start + 1:
        # Make sure we don't span differently indented code blocks
        # by using the BlockFinder helper used which inspect.getsource() uses itself.
        block_finder = inspect.BlockFinder()
        # If we start with an indented line, put blockfinder to "started" mode.
        block_finder.started = (
            bool(source.lines[start]) and source.lines[start][0].isspace()
        )
        # Instead of generator expression, create a list for the slice up front for memory locality
        lines_to_tokenize = source.lines[start:end]
        # This generator is fast, don't rewrite using map or list unnecessarily
        it = (line + "\n" for line in lines_to_tokenize)
        try:
            # It's faster to avoid the lambda in tokenize.generate_tokens; use a local generator
            it_next = it.__next__
            for tok in tokenize.generate_tokens(it_next):
                block_finder.tokeneater(*tok)
        except (inspect.EndOfBlock, IndentationError):
            end = block_finder.last + start
        except Exception:
            pass

    # The end might still point to a comment or empty line, correct it.

    # The end might still point to a comment or empty line, correct it.
    # Mem-efficient: avoid repeated attr lookups for .lines
    lines = source.lines
    while end:
        line = lines[end - 1].lstrip()
        if line.startswith("#") or not line:
            end -= 1
        else:
            break
    return astnode, start, end


@lru_cache(maxsize=128)
def _parse_ast_from_source(source_text: str) -> ast.AST:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.parse(source_text, "source", "exec")
