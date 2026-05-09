# datamind/cli/main.py

"""Datamind CLI入口"""

import argparse

from datamind.cli.model import model_command


def main():
    parser = argparse.ArgumentParser("datamind CLI")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # =========================
    # model subcommand
    # =========================
    model_parser = subparsers.add_parser("model", help="模型管理")

    model_sub = model_parser.add_subparsers(dest="action", required=True)

    model_sub.add_parser("register", help="注册模型")
    model_sub.add_parser("list", help="模型列表")
    model_sub.add_parser("delete", help="删除模型")

    args = parser.parse_args()

    if args.command == "model":
        model_command(args)


if __name__ == "__main__":
    main()