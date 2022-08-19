# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

from dataclasses import dataclass
from typing import Union, Optional, Tuple
import functools


# Copied from https://github.com/Gowee/nlcpd/blob/53d549827bde29220fd2b64d0d7444863d1fb410/crawler/nlccrawler/items.py
def mongo_item(collection_name=None, to__id=None, upsert_index=None):
    """
    A decorator for Item classes that instructs the TxMongoPipeline to store
    items properly

    Args:
        collection_name : Required. O.W., `TxMongoPipeline` just ignores the
            item.
        to__id : a field to be renamed to `_id`, which is optional.
        upsert_index : a tuple of fields be used as the criteria when upserting.
            Without this, upserting is disabled.
    """

    def wrap(cls):
        # TODO: validate fields specified in upsert_index
        # for field in upsert_index:
        #     if not hasattr(cls, field):
        #         raise KeyError(f"The field {field} specified in upsert_index does not exist for {cls}")
        @functools.wraps(cls, updated=())
        class Wrapper(cls):
            _collection_name = collection_name or cls.__name__
            _to__id = to__id
            _upsert_index = upsert_index

        return Wrapper

    return wrap


@mongo_item(collection_name="books", to__id="id", upsert_index=("_id",))
@dataclass
class BookItem:
    @dataclass
    class VolumeItem:
        name: str
        swf_url: str
        cover_image_url: str
    recNo: int # id?
    long_name: str
    misc_metadata: dict[str, str]
    volumes: list["VolumeItem"]
    of_itemno: str
    of_itemsonno: str
