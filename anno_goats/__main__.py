from itertools import chain
import logging

import lxml.etree

from anno_goats.assets import AssetsIndexed


logger = logging.getLogger(__name__)

flatten = chain.from_iterable


def comma_delimited_guids(s):
    return [int(guid.strip()) for guid in s.split(',')]

def main():
    import argparse

    # import sys, platform
    # if platform.system() == 'Windows':
    #     sys.stdout.reconfigure(encoding='utf-8')  # stupid windows shit? doesn't actually work anyway

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', help='Verbosity, more of these increases logging.', action='count', default=0)
    parser.add_argument('-d', '--depth', type=int, default=-1)
    parser.add_argument('input', type=argparse.FileType('r', encoding="utf-8"))
    parser.add_argument('--items', type=comma_delimited_guids, nargs="*", default=[], action='extend')
    parser.add_argument('--pools', type=comma_delimited_guids, nargs="*", default=[], action='extend')
    parser.add_argument('-o', '--output', default='-', type=argparse.FileType('w', encoding="utf-8"))
    args = parser.parse_args()

    log_level = {0: logging.WARNING, 1: logging.INFO}.get(args.v, logging.DEBUG)
    logging.basicConfig(level=log_level, format="%(asctime)s\t%(levelname)s\t%(message)s")

    logger.info("Logging level set to %s.", log_level)

    logger.info("reading xml")
    doc = lxml.etree.parse(args.input)

    logger.info("building asset index")
    assets = AssetsIndexed.from_xml(doc, filename=args.input)
    logger.info("woot")

    for guid in flatten(args.pools):
        pool = assets.in_rewards_tree(guid)
        pool.display(depth=args.depth, file=args.output)

    for guid in flatten(args.items):
        reward = assets.reward_tree(guid)
        reward.display(depth=args.depth, file=args.output)


if __name__ == "__main__":
    main()
