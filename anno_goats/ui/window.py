from os import fstat
import sys
import logging
import traceback
from contextlib import contextmanager
from functools import wraps
from enum import Enum

import lxml.etree

from PySide6.QtCore import Slot, Signal, QThread, QAbstractListModel, QModelIndex
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QCompleter, QHeaderView, QLabel, QPushButton, QFileDialog, QProgressDialog, QMessageBox
from PySide6.QtGui import Qt, QShortcut, QKeySequence, QValidator

from anno_goats.assets import AssetsIndexed, asset_guid, asset_name, RewardPoolItem
from anno_goats.ui.assets import RewardTree


logger = logging.getLogger(__name__)

SPECIALISTS_LEGENDARY = 192975


class _unchanged(object):
    pass


class LoadCancelled(Exception):
    pass


class AssetThreadLoader(QThread):

    progress = Signal(int, int)

    def __init__(self, filename, **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        self.assets = None
        self.exception = None
        self.canceled = False

    @Slot()
    def cancel(self):
        self.canceled = True

    def run(self):
        try:
            self._run()
        except LoadCancelled:
            pass
        except Exception as e:
            self.exception = e

    def _run(self):
        with open(self.filename, 'r', encoding='utf-8') as file:
            done = 0
            size = fstat(file.fileno()).st_size
            read = file.read

            self.progress.emit(done, size)

            def read_proxy(*args):
                if self.canceled:
                    raise LoadCancelled

                nonlocal done
                buf = read(*args)
                done += len(buf)
                self.progress.emit(done, size)
                return buf

            # this is not technically reliable, it just happens to be that the
            # lxml parser will process the last chunk before reading the next
            file.read = read_proxy

            logger.info("reading xml")
            doc = lxml.etree.parse(file)

        self.progress.emit(0, 0)

        logger.info("building asset index")
        assets = AssetsIndexed.from_xml(doc, filename=self.filename)

        self.progress.emit(1, 1)

        logger.info("found %s assets", len(assets.index))
        self.assets = assets


def load_assets(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        logger.info("reading xml")
        doc = lxml.etree.parse(file)

    logger.info("building asset index")
    assets = AssetsIndexed.from_xml(doc, filename=filename)

    logger.info("found %s assets", len(assets.index))
    return assets


def load_assets_with_progressbar(filename: str, **kwargs) -> AssetsIndexed:
    """ returns None if the progress bar is closed before completing
    """
    # show the dialog if it's estimated to take longer than 300ms, (default 4000ms)
    dialog = QProgressDialog(labelText=filename, minimumDuration=300, autoClose=False, **kwargs)
    dialog.setCancelButton(None)

    load = AssetThreadLoader(filename)

    @load.progress.connect
    def update_progress(done, total):
        if dialog.isVisible():
            dialog.setMaximum(total)
            dialog.setValue(done)

    dialog.canceled.connect(load.cancel)
    load.finished.connect(dialog.accept)

    load.start()
    dialog.exec()
    dialog.cancel()
    load.wait()

    if load.exception:
        raise load.exception

    return load.assets


def show_exception(where: str = '', exc_info=None):
    logger.exception(where)

    if exc_info is None:
        exc_info = sys.exc_info()

    exc_type, exc_value, _ = exc_info

    msg = f"oh no :C\n{Qt.convertFromPlainText(str(exc_value))}\n"
    if where:
        msg += f"<i>{Qt.convertFromPlainText(where)}</i>"

    details = "".join(traceback.format_exception(*exc_info))

    msg = QMessageBox(
        icon=QMessageBox.Critical,
        # stupid hack to make the thing wider
        text=f'{msg: <120}',
        parent=None,
        detailedText=details,
        textFormat=Qt.RichText
    )
    msg.exec()


def prompt_for_assets_path(**kwargs):
    dialog = QFileDialog(caption="path to assets.xml", **kwargs)
    if dialog.exec():
        for filename in dialog.selectedFiles():
            return filename


def file_paths_from_mime(mime):
    return (url.toLocalFile() for url in mime.urls() if url.isLocalFile())


def generator_length(g):
    return sum(1 for _ in g)


class Mode(Enum):
    ItemsInThisPool = "show items in selected pool"
    PoolsWithThisItem = "show pools with selected item"
    
    def load(self, assets: AssetsIndexed, guid: int) -> RewardPoolItem:
        if self == self.ItemsInThisPool:
            return assets.reward_tree(guid)
        elif self == self.PoolsWithThisItem:
            return assets.in_rewards_tree(guid)
        else:
            raise ValueError(self)



class IsAssetValidator(QValidator):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.assets = None

    def validate(self, s: str, pos: int) -> QValidator.State:
        if self.assets is None or not s:
            return QValidator.Intermediate

        try:
            guid = int(s)
        except ValueError:
            logger.debug("not an integer: %s", s)
            return QValidator.Invalid

        if guid in self.assets.index:
            logger.debug("asset found: %s", guid)
            return QValidator.Acceptable
        else:
            logger.debug("asset not found: %s", s)
            return QValidator.Intermediate


class AssetGuidModel(QAbstractListModel):
    def __init__(self, assets, **kwargs):
        super().__init__(**kwargs)
        self.items = [(f'{guid} - {name}', guid)
                      for guid, name in assets.aux.items()]

    def data(self, index, role=Qt.DisplayRole):
        if index.parent().isValid():
            return

        if role == Qt.DisplayRole:
            v, _ = self.items[index.row()]
            return v

        if role == Qt.UserRole:
            _, v = self.items[index.row()]
            return v

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0 or parent.isValid():
            return 0
        else:
            return len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return 1


class Window(QWidget):
    def __init__(self, mode=Mode.ItemsInThisPool, **kwargs):
        super().__init__(**kwargs)

        self.setAcceptDrops(True)

        self._assets = None
        self._pool = None
        self._mode = mode
        self._headers_need_resize = True

        self.guid = QComboBox(parent=self)
        self.filename = QLabel(parent=self)
        self.open = QPushButton('open...', parent=self, shortcut=QKeySequence("ctrl+o"))
        self.open.clicked.connect(self.show_file_dialog)

        self.header = QHBoxLayout()
        self.header.addWidget(self.guid, stretch=1)
        self.header.addWidget(self.filename, stretch=1)
        self.header.addWidget(self.open)

        self.tree = RewardTree(root=None, parent=self)
        self.tree.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.tree.addAction(Mode.ItemsInThisPool.value) \
            .triggered.connect(self._load_items_in_selected_pool)
        self.tree.addAction(Mode.PoolsWithThisItem.value) \
            .triggered.connect(self._load_pools_with_selected_item)

        self.search = QLineEdit(placeholderText='filter GUID or name', parent=self)
        self.detail = QLabel(parent=self)

        self.footer = QHBoxLayout()
        self.footer.addWidget(self.search, stretch=1)
        self.footer.addWidget(self.detail)

        self.layout = QVBoxLayout(self)
        self.layout.addLayout(self.header)
        self.layout.addWidget(self.tree)
        self.layout.addLayout(self.footer)

        self.guid.activated.connect(self._load_guid_if_changed)
        # this is slow so doing this on textChanged sucks
        # self.search.textChanged.connect(self.tree.filter.setFilterWildcard)
        self.search.editingFinished.connect(self._do_search)

        self._refresh_detail_text(self._pool)

        QShortcut(QKeySequence('ctrl+f'), self) \
            .activated.connect(self._focus_search)

        QShortcut(QKeySequence('ctrl+r'), self) \
            .activated.connect(self._reload_assets)

        QShortcut(QKeySequence('ctrl+k'), self) \
            .activated.connect(self._load_everything)

    @Slot()
    def _load_everything(self):
        if self._assets is None:
            return

        self.reload(pool=self._assets.get_everything())

    def reload(self, /, assets: AssetsIndexed=_unchanged, pool: RewardPoolItem=_unchanged, mode: Mode=_unchanged):
        if assets == self._assets:
            assets = _unchanged

        if mode == self._mode:
            mode = _unchanged
 
        if pool == self._pool:
            pool = _unchanged

        if mode is not _unchanged:
            self._mode = mode

        if assets is not _unchanged:
            self._assets = assets

            self.guid.clear()
            if assets is not None:
                self.guid.addItem("everything", AssetsIndexed.EVERYTHING)

                for row, (guid, name) in enumerate(assets.aux.items()):
                    self.guid.addItem(f'{guid} - {name}', userData=guid)

            self.filename.setText(assets.filename)

            if pool is _unchanged and assets is not None: 
                # when loading new assets and no pool is specified ...

                if self._pool is None:
                    # open the default pool
                    try:
                        pool = self._mode.load(assets, SPECIALISTS_LEGENDARY)
                    except Exception:
                        # ... but silently fail?
                        logger.exception(f"loading GUID {SPECIALISTS_LEGENDARY}")

                else:
                    # reopen the current pool
                    try:
                        pool = self._mode.load(assets, self._pool.guid)
                    except Exception:
                        pool = None
                        show_exception(f"loading GUID {self._pool.guid}")


        if pool is not _unchanged:
            self._pool = pool

            self.tree.reload(self._pool)
            self._refresh_detail_text(self._pool)
            if self._pool is not None:
                index = self.guid.findData(self._pool.guid)
                if index >= 0:
                    self.guid.setCurrentIndex(index)

        if self._pool is not None and self._headers_need_resize:
            self._headers_need_resize = False
            # TODO ensure we're visible?
            self.tree.header().resizeSections(QHeaderView.ResizeToContents)

    def _refresh_detail_text(self, pool):
        if pool is None:
            self.detail.setText('view asset by GUID in the top left')
        else:
            total = generator_length(pool.iter_all())
            leaf = generator_length(pool.iter_leafs())
            self.detail.setText(f'total items {total} | leaf items {leaf}')

    @Slot()
    def _load_items_in_selected_pool(self):
        if (item := self.tree.selected_item()) is None:
            return

        if self._assets is None:
            return

        mode = Mode.ItemsInThisPool
        try:
            pool = mode.load(self._assets, item.guid)
        except Exception:
            show_exception(f"loading GUID {item.guid}")
        else:
            self.reload(pool=pool, mode=mode)

    @Slot()
    def _load_pools_with_selected_item(self):
        if (item := self.tree.selected_item()) is None:
            return

        mode = Mode.PoolsWithThisItem
        try:
            pool = mode.load(self._assets, item.guid)
        except Exception:
            show_exception(f"loading GUID {item.guid}")
        else:
            self.reload(pool=pool, mode=mode)

    @Slot()
    def _reload_assets(self):
        """ reload assets from current filename """
        if self._assets is None:
            return

        try:
            assets = load_assets_with_progressbar(self._assets.filename, parent=self)
        except Exception:
            show_exception(f"loading {self._assets.filename}")
        else:
            if assets is not None:
                self.reload(assets=assets)

    @Slot(int)
    def _load_guid_if_changed(self, index):
        """ Load a different pool from self.guid.text() """
        
        if self._assets is None:
            return

        if self._pool is None:
            return

        new_guid = self.guid.itemData(index)
        if new_guid is None:
            return

        if self._pool.guid == new_guid:
            return

        try:
            if new_guid is AssetsIndexed.EVERYTHING:
                pool = self._assets.get_everything()
            else:
                pool = self._mode.load(self._assets, new_guid)
        except Exception:
            show_exception(f"loading GUID {new_guid}")
        else:
            self.reload(pool=pool)

    @Slot()
    def show_file_dialog(self):
        if self._assets is None:
            directory = None
        else:
            directory = self._assets.filename

        filename = prompt_for_assets_path(directory=directory, parent=self)
        if filename is None:
            return

        try:
            assets = load_assets_with_progressbar(filename)
        except Exception:
            show_exception(f"loading {filename}")
            return

        if assets is None:
            return

        self.reload(assets=assets)

        return self._assets

    @Slot()
    def _do_search(self):
        self.tree.filter.setFilterWildcard(self.search.text())

    @Slot()
    def _focus_search(self):
        self.search.setFocus()

    def dragEnterEvent(self, event):
        if any(file_paths_from_mime(event.mimeData())):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for path in file_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()

            try:
                assets = load_assets_with_progressbar(path, parent=self)
            except Exception:
                show_exception(f"loading {path}")
            else:
                if assets is not None:
                    self.reload(assets=assets)

            break  # TODO open new windows for each file?
