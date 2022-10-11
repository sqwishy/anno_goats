from dataclasses import field, dataclass
from itertools import chain, repeat
from functools import wraps
from typing import Any
import logging
import weakref


logger = logging.getLogger(__name__)


def cached_generator(func):
    cache_attr = f'_cached_{func.__name__}'

    @wraps(func)
    def inner(self):
        if (v := getattr(self, cache_attr, None)) is None:
            v = list(func(self))
            setattr(self, cache_attr, v)
        return v

    return inner


def asset_guid(asset):
    if (guid := asset.find("Values/Standard/GUID")) is not None:
        return int(guid.text)


def asset_name(asset):
    if (name := asset.find("Values/Standard/Name")) is not None:
        return name.text


def asset_english_text(asset):
    return asset.findtext("Values/Text/LocaText/English/Text")


def asset_index(doc):
    """ Expected to take hundreds of milliseconds on anno's assets.xml
    """
    index = {}
    for n in doc.xpath("//Assets/Asset[Values/Item or Values/RewardPool]"):
        if (guid := asset_guid(n)) is not None:
            index[guid] = n
    return index


@dataclass(eq=False)
class AssetsIndexed(object):
    doc: Any
    index: Any
    aux: str
    filename: str

    class EVERYTHING(object):
        pass

    def __len__(self):
        return len(self.index)

    @classmethod
    def from_xml(cls, doc, /, filename):
        index = asset_index(doc)
        aux = {guid: asset_name(asset) for guid, asset in index.items()}
        return cls(doc=doc, index=index, aux=aux, filename=filename)

    def get_everything(self):
        children = [RewardPoolItem(guid=guid, name=name) for guid, name in self.aux.items()]
        return RewardPoolItem(self.EVERYTHING, '', children=children)

    @cached_generator
    def reward_pools(self):
        for asset in self.index.values():
            if asset.find("Values/RewardPool") is not None:
                yield asset

    def reward_tree(self, guid):
        """ build a tree of the reward items under the given RewardPool
        """
        return self._reward_pool_tree(guid, chance_from_root=1)

    def _reward_pool_tree(self, guid, **kwargs):
        try:
            asset = self.index[guid]
        except KeyError:
            raise ValueError(f"no asset for {guid}")

        parent = RewardPoolItem(
            guid=guid,
            name=self.aux[guid],
            english=asset_english_text(asset),
            **kwargs,
        )

        linkweights = [
            (
                int(reward.findtext("ItemLink")),
                int(reward.findtext("Weight") or 1)
            )
            for reward in asset.xpath("Values/RewardPool//Item[ItemLink][not(Weight=0)]")
        ]

        pool_weight = sum(weight for (_, weight) in linkweights)

        parent.children = [
            self._reward_pool_tree(
                link,
                weight=weight,
                chance_from_parent=weight / pool_weight,
                chance_from_root=parent.chance_from_root * weight / pool_weight,
                parent=weakref.ref(parent),
            )
            for (link, weight) in linkweights
        ]

        return parent

    def in_rewards_tree(self, guid: int):
        """ build a tree of RewardPool containing this item
        """
        return self._in_rewards_tree(guid)

    def _in_rewards_tree(self, guid: int, **kwargs):
        parent = RewardPoolItem(
            guid=guid,
            name=self.aux[guid],
            english=asset_english_text(self.index[guid]),
            **kwargs,
        )

        parent.children = [
            self._in_rewards_tree(
                guid=asset_guid(asset),
                parent=weakref.ref(parent),
                weight=int(item.findtext("Weight") or 1),
            )
            for (asset, item) in self.in_rewards(guid)
        ]

        return parent

    def in_rewards(self, guid: int):
        """ generator of assets & item pairs where the asset is a reward pool
        containing item and item is an itemlink to the given guid

        - can yield the same pool multiple times if this item is listed in it
          more than once
        - includes pools where guid is an item with zero weight
        """
        for (asset, item, link) in self.all_reward_items():
            if link == guid:
                yield asset, item

    @cached_generator
    def all_reward_items(self):
        for asset in self.reward_pools():
            for item in asset.xpath("Values/RewardPool/ItemsPool/Item"):
                if (link := item.findtext("ItemLink")):
                    yield asset, item, int(link)
 

@dataclass(eq=False)
class RewardPoolItem(object):
    """ RewardPool with children coming from RewardPool/Item elements
    """
    guid: int
    name: str
    english: str = field(default=None)
    weight: Any = field(default=None)
    children: Any = field(default_factory=list)
    parent: Any = field(default=lambda: None)
    chance_from_parent: Any = field(default=None)
    chance_from_root: Any = field(default=None)

    __hash__ = object.__hash__

    @property
    def root(self):
        if (parent := self.parent()):
            return parent.root
        else:
            return self

    def iter_all(self):
        yield self
        for child in self.children:
            yield from child.iter_all()

    def iter_leafs(self):
        if self.children:
            for child in self.children:
                yield from child.iter_leafs()
        else:
            yield self

    def __len__(self):
        return len(self.children)

    def display(self, depth=-1, file=None, indent=()):
        i = "".join(map(next, indent)) + " " if indent else ""
        weight = '*' if self.weight is None else self.weight
        print(f"{i}{self.guid} [{weight}] {self.name}", file=file)

        if depth == 0:
            return

        for e, child in enumerate(self.children):
            if e < len(self.children) - 1:
                indent_this = chain(("|──",), repeat("|  "))
            else:
                indent_this = chain(("└──",), repeat("   "))
            child.display(depth=depth-1, file=file, indent=(*indent, indent_this))
