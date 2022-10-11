from PySide6.QtCore import Qt, Slot, QAbstractItemModel, QPersistentModelIndex, QModelIndex, QSortFilterProxyModel
from PySide6.QtWidgets import QTreeView, QWidget, QHeaderView, QApplication
from PySide6.QtGui import QKeySequence, QPalette, QBrush
from operator import attrgetter
from dataclasses import dataclass

FILTER_ROLE = Qt.UserRole


@dataclass
class Column(object):
    name: str
    getter: 'typing.Any'
    display: 'typing.Any' = None


def display_percentage(v):
    if v is not None:
        return f'{v * 100.0:.04}%'


def nonzero(v):
    if v:
        return v


class RewardTreeModel(QAbstractItemModel):
    def __init__(self, root, **kwargs):
        super().__init__(**kwargs)
        self.roots = [] if root is None else [root]
        self.columns = [
            Column("GUID", attrgetter('guid')),
            Column("Name", attrgetter('name')),
            Column("English", attrgetter('english')),
            Column("% in parent", attrgetter('chance_from_parent'), display_percentage),
            Column("% in root", attrgetter('chance_from_root'), display_percentage),
            Column("Weight", attrgetter('weight')),
            Column("Length", len, nonzero),
        ]
        self.muted = QApplication.instance().palette().color(QPalette.PlaceholderText)

    def reload(self, root):
        self.reload_list([] if root is None else [root])

    def reload_list(self, roots: list):
        self.beginResetModel()
        self.roots = roots[:]
        self.endResetModel()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[section].name

    def index(self, row, column, parent=QModelIndex()):
        parent_item = parent.internalPointer()
        if parent_item is None:
            if parent.column() > 0:
                return QModelIndex()
            else:
                return self.createIndex(row, column, self.roots[row])
        else:
            return self.createIndex(row, column, parent_item.children[row])

    def parent(self, index):
        """ Parent of the model item with the given index.

        If the item has no parent, an invalid QModelIndex is returned.
        """
        if (child := index.internalPointer()) is None:
            return QModelIndex()

        if (item := child.parent()) is None:
            return QModelIndex()

        if (parent := item.parent()) is None:
            row = self.roots.index(item)
        else:
            row = parent.children.index(item)

        return self.createIndex(row, 0, item)

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0

        item = parent.internalPointer()
        if item is None:
            return len(self.roots)
        else:
            return len(item.children)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if (item := index.internalPointer()) is None:
            return

        column = self.columns[index.column()]

        if role == Qt.DisplayRole:
            value = column.getter(item)
            if column.display:
                value = column.display(value)
            return value

        if role == Qt.ForegroundRole:
            if item.weight == 0:
                return QBrush(self.muted)

        elif role == FILTER_ROLE:
            return f"{item.guid} {item.name} {item.english}"


class RewardTree(QTreeView):
    def __init__(self, root, **kwargs):
        super().__init__(uniformRowHeights=True, expandsOnDoubleClick=False, selectionMode=QTreeView.ContiguousSelection, **kwargs)
        self._model = RewardTreeModel(root, parent=self)

        self.filter = QSortFilterProxyModel(parent=self, filterRole=FILTER_ROLE)
        self.filter.setRecursiveFilteringEnabled(True)
        self.filter.setSourceModel(self._model)
        self.setModel(self.filter)

        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(1, QHeaderView.Stretch)

        self.expanded.connect(self._add_exanded)
        self.collapsed.connect(self._remove_expanded)

        self._expanded = set()
        self.expandAll()

        self.model().rowsInserted.connect(self._maybe_expand_new_rows)
        self.model().modelAboutToBeReset.connect(self._reset_exanded)

    def _index_item(self, index):
        assert index.model() == self.filter
        return self.filter.mapToSource(index).internalPointer()

    @Slot(QModelIndex)
    def _add_exanded(self, index):
        self._expanded.add(self._index_item(index))

    @Slot(QModelIndex)
    def _remove_expanded(self, index):
        self._expanded.remove(self._index_item(index))

    @Slot()
    def _reset_exanded(self):
        self._expanded.clear()

    @Slot(QModelIndex, int, int)
    def _maybe_expand_new_rows(self, parent, first, last):
        model = self.model()

        for row in range(first, last + 1):
            index = model.index(row, 0, parent)
            if self._index_item(index) in self._expanded:
                self.expand(index)

            if (children := model.rowCount(index)) > 0:
                self._maybe_expand_new_rows(index, 0, children - 1)

    def reload(self, v):
        self._model.reload(v)
        self.expandAll()

    def selected_item(self):
        for index in self.selectedIndexes():
            return self._index_item(index)

    # TODO this might return the same item multiple times as one row is
    # selected on each column?
    # def selected_items(self):
    #     return [self._index_item(index) for index in self.selectedIndexes()]

    def selection_to_strings(self):
        column = self.currentIndex().column()
        for index in self.selectedIndexes():
            if index.column() == column:
                data = self.model().data(index, role=Qt.DisplayRole)
                if data is None:
                    yield ""
                else:
                    yield str(data)

    def keyPressEvent(self, event):
        if event == QKeySequence.Copy:
            if (text := "\n".join(self.selection_to_strings())):
                QApplication.instance().clipboard().setText(text)
            event.accept()
        else:
            super().keyPressEvent(event)
