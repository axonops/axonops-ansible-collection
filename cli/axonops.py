import sys

from axonopscli.application import Application


def main() -> int:
    argv = sys.argv[1:]

    app = Application()
    app.run(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
