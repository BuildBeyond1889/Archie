"""A command-line tool. Run it with:  python main.py --help"""
import argparse
import sys
# archie:imports


def cmd_hello(args):
    print("Hello, %s!" % args.name)


def main(argv=None):
    p = argparse.ArgumentParser(description="What this tool does, in one line.")
    sub = p.add_subparsers(dest="command")

    h = sub.add_parser("hello", help="say hello")        # each command is a sub-parser
    h.add_argument("--name", default="world")
    h.set_defaults(run=cmd_hello)

    args = p.parse_args(argv)
    if not getattr(args, "run", None):
        p.print_help()
        return 1
    args.run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
