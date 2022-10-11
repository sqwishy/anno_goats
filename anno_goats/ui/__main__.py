import logging
import pathlib
import platform
import sys

import lxml.etree

from PySide6.QtWidgets import QApplication

from anno_goats.ui.window import Mode, Window, load_assets_with_progressbar, show_exception, SPECIALISTS_LEGENDARY


logger = logging.getLogger(__name__)

is_frozen = getattr(sys, 'frozen', False)

if platform.system() == 'Windows':
    runtime_path = pathlib.Path.home() / "AppData" / "Roaming" / "anno-goats"
else:
    runtime_path = None


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', help='Verbosity, more of these increases logging.', action='count', default=0)
    parser.add_argument('path', nargs='?')
    parser.add_argument('--guid', type=int, default=SPECIALISTS_LEGENDARY)
    parser.add_argument('qt_args', nargs='*', action='extend', default=sys.argv[:1])
    args = parser.parse_args()

    log_level = {0: logging.WARNING, 1: logging.INFO}.get(args.v, logging.DEBUG)
    logging.basicConfig(level=log_level, format="%(asctime)s\t%(levelname)s\t%(message)s")

    if is_frozen and runtime_path is not None:
        runtime_path.mkdir(exist_ok=True)
        logfile = str(runtime_path / 'logging.txt')
        logger.info("Logging to %s", logfile)
        handler = logging.FileHandler(logfile)
        logging.getLogger().addHandler(handler)

    logger.info("Logging level set to %s.", log_level)

    app = QApplication(args.qt_args)

    assets = None
    pool = None
    mode = Mode.ItemsInThisPool

    widget = Window(mode=mode)
    widget.resize(800, 600)
    widget.show()

    if args.path is None:
        assets = widget.show_file_dialog()

    else:
        try:
            assets = load_assets_with_progressbar(args.path)
        except Exception:
            show_exception(f"loading {args.path}")

    if assets is not None:
        try:
            pool = mode.load(assets, args.guid)
        except Exception:
            show_exception(f"loading GUID {args.guid}")

    widget.reload(assets=assets, pool=pool, mode=mode)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
