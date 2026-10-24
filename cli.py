"""Command line for the human steps:  python -m app.cli list | review <id> --reviewer NAME | discover

`review` is the gate that lets a scheme be shown to farmers. It records who reviewed and when, so a reviewer
must read the scheme's sources first."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import get_settings
from .db import make_repository
from .schemes import load_schemes, review_scheme, unreview_scheme
from .tinyfish import make_web_client


def _list() -> int:
    for s in load_schemes(get_settings()):
        status = f"reviewed by {s.reviewed_by} on {s.reviewed_at}" if s.reviewed else "NOT reviewed"
        print(f"{s.id:22} {status:42} {s.name}")
    return 0


def _review(ids: list[str], reviewer: str, everything: bool) -> int:
    settings = get_settings()
    targets = [s.id for s in load_schemes(settings) if not s.reviewed] if everything else ids
    if not targets:
        print("nothing to review")
        return 0
    for scheme_id in targets:
        try:
            scheme = review_scheme(settings, scheme_id, reviewer)
        except KeyError:
            print(f"no such scheme: {scheme_id}", file=sys.stderr)
            return 1
        print(f"reviewed {scheme.id} ({scheme.name}) as {scheme.reviewed_by} on {scheme.reviewed_at}")
        for src in scheme.sources:
            print(f"    source: {src.url}")
    return 0


def _discover() -> int:
    from .discovery import discover

    settings = get_settings()
    web = make_web_client(settings, make_repository(settings))
    created = asyncio.run(discover(web, settings))
    if not created:
        print("no new schemes found")
    for s in created:
        print(f"candidate written (reviewed: false): {s.id}  deadline={s.deadline or 'none cited'}  {s.apply_url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="KhetKaaj scheme review tools")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="show every scheme and whether a person has reviewed it")
    rv = sub.add_parser("review", help="mark scheme(s) reviewed by a named person")
    rv.add_argument("ids", nargs="*")
    rv.add_argument("--reviewer", required=True, help="your name; recorded in the file")
    rv.add_argument("--all", action="store_true", help="review every unreviewed scheme (read each source first)")
    un = sub.add_parser("unreview", help="withdraw a review")
    un.add_argument("ids", nargs="+")
    sub.add_parser("discover", help="search for new scheme notices and write candidates (reviewed: false)")
    args = parser.parse_args(argv)

    if args.cmd == "list":
        return _list()
    if args.cmd == "review":
        if not args.ids and not args.all:
            parser.error("give scheme ids or --all")
        return _review(args.ids, args.reviewer, args.all)
    if args.cmd == "unreview":
        for scheme_id in args.ids:
            unreview_scheme(get_settings(), scheme_id)
            print(f"unreviewed {scheme_id}")
        return 0
    return _discover()


if __name__ == "__main__":
    raise SystemExit(main())
