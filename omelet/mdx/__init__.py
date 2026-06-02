from .parser import make_parser

__all__ = ["make_parser", "compile_mdx"]


def compile_mdx(path):
    from .compiler import compile_mdx_path
    return compile_mdx_path(path)
