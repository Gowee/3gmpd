#!/usr/bin/env python3
import os.path
import itertools
import subprocess
import json
import logging
from io import BytesIO
import os
import functools
import re
import sys
from itertools import chain
from more_itertools import peekable

import requests
import yaml
import mwclient

# from getbook import getbook

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "config.yml")
POSITION_FILE_PATH = os.path.join(os.path.dirname(__file__), ".position")
DATA_DIR = os.path.join(os.path.dirname(__file__), "../crawler/")
RETRY_TIMES = 3

USER_AGENT = "3gmpdbot/0.0 (+https://github.com/gowee/3gmpd)"

# RESP_DUMP_PATH = "/tmp/wmc_upload_resp_dump.html"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def call(command, *args, **kwargs):
    kwargs["shell"] = True
    return subprocess.check_call(command, *args, **kwargs)


def load_position(name):
    logger.info(f'Loading position from {POSITION_FILE_PATH + "." + name}')
    if os.path.exists(POSITION_FILE_PATH + "." + name):
        with open(POSITION_FILE_PATH + "." + name, "r") as f:
            return f.read().strip()
    else:
        return None


def store_position(name, position):
    with open(POSITION_FILE_PATH + "." + name, "w") as f:
        f.write(position)


def retry(times=RETRY_TIMES):
    def wrapper(fn):
        tried = 0

        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            while True:
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    nonlocal tried
                    tried += 1
                    if tried == times:
                        raise Exception(f"Failed finally after {times} tries") from e
                    logger.debug(f"Retrying {fn}")

        return wrapped

    return wrapper


def getbook(url):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT})
    assert len(resp.content) != 0, "Got empty file"
    if "Content-Length" in resp.headers:
        # https://blog.petrzemek.net/2018/04/22/on-incomplete-http-reads-and-the-requests-library-in-python/
        expected_size = int(resp.headers["Content-Length"])
        actual_size = resp.raw.tell()
        assert (
            expected_size == actual_size
        ), f"Incomplete download: {actual_size}/{expected_size}"
    return resp.content


def main():
    with open(CONFIG_FILE_PATH, "r") as f:
        config = yaml.safe_load(f.read())

    if len(sys.argv) < 2:
        exit(
            f"Not batch specified.\n\nAvailable: {', '.join(list(config['batches'].keys()))}"
        )
    batch_name = sys.argv[1]

    username, password = config["username"], config["password"]
    site = mwclient.Site("commons.wikimedia.org")
    site.login(username, password)
    site.requests["timeout"] = 125
    site.chunk_size = 1024 * 1024 * 64

    logger.info(f"Signed in as {username}")

    def getopt(item, default=None):  # get batch config or fallback to global config
        return config["batches"][batch_name].get(item, config.get(item, default))

    with open(os.path.join(DATA_DIR, batch_name + ".json")) as f:
        books = json.load(f)
    template = getopt("template")
    batch_link = getopt("link") or getopt("name")

    booknavi = getopt("booknavi")

    last_position = load_position(batch_name)

    if last_position is not None:
        books = iter(books)
        logger.info(f"Last processed: {last_position}")
        next(
            itertools.dropwhile(
                lambda book: str(book["relicno"]) != last_position, books
            )
        )  # lazy!
        # TODO: peek and report?

    failcnt = 0

    for book in books:
        title = book["oldname"]
        category_name = "Category:" + title
        byline = book["author"]
        if getopt("apply_tortoise_shell_brackets_to_starting_of_byline", False):
            # e.g. "(???)??????,(???)????????????   (???)?????????"
            byline = re.sub(
                r"^([???(???[][??????][]???)???])?[???(???[](.{0,3}?)[]???)???]",
                r"\1???\2???",
                byline,
            )
        volurls = book["p_resourceurl"].split(",")

        def genvols():
            for ivol, volurl in enumerate(volurls):
                # pagename = "File:" + book['name'] + ".pdf"
                volume_name = f"???{ivol+1}???" if len(volurls) > 1 else ""
                volume_name_wps = (
                    (" " + volume_name) if volume_name else ""
                )  # with preceding space
                filename = f'{book["name"]}{volume_name_wps}.pdf'
                pagename = "File:" + filename
                assert all(char not in set(r'["$*|\]</^>@#') for char in pagename)
                comment = f'Upload {book["name"]}{volume_name_wps} ({1+ivol}/{len(volurls)}) by {book["author"]} (batch task; 3gm; {batch_link}; [[{category_name}|{title}]])'
                yield ivol + 1, volume_name, filename, pagename, volurl, comment

        volsit = peekable(genvols())
        prev_filename = None
        for nth, volume_name, filename, pagename, volurl, comment in volsit:
            try:
                next_filename = volsit.peek()[2]
            except StopIteration:
                next_filename = None
            additional_fields = "\n".join(
                f"  |JSONFIELD-{k}={v}" for k, v in book.items()
            )
            category_page = site.pages[category_name]
            # TODO: for now we do not create a seperated category suffixed with the edition
            if not category_page.exists:
                category_wikitext = (
                    """{{Wikidata Infobox}}
{{Category for book|zh}}
{{zh|%s}}

[[Category:Chinese-language books by title]]
    """
                    % title
                )
                category_page.edit(
                    category_wikitext,
                    f"Creating (batch task; 3gm; {batch_link})",
                )
            volume_wikitext = f"""=={{{{int:filedesc}}}}==
{{{{{booknavi}|prev={prev_filename or ""}|next={next_filename or ""}|nth={nth}|total={len(volurls)}|type={book["type"]}|sid={book["sid"]}|recno={book["recno"]}|relicno={book["relicno"]}}}}}
{{{{{template}
  |byline={byline}
  |volume={volume_name}
{additional_fields}
}}}}

[[{category_name}]]
    """
            page = site.pages[pagename]
            try:
                if not page.exists:
                    logger.info(f"Downloading {volurl}")
                    binary = getbook(volurl)
                    logger.info(f"Uploading {pagename} ({len(binary)} B)")

                    @retry()
                    def do1():
                        r = site.upload(
                            BytesIO(binary),
                            filename=filename,
                            description=volume_wikitext,
                            comment=comment,
                        )
                        assert (r or {}).get("result", {}) == "Success" or (
                            r or {}
                        ).get("warnings", {}).get("exists"), f"Upload failed {r}"

                    do1()
                else:
                    if getopt("skip_on_existing", False):
                        logger.debug(f"{pagename} exists, skipping")
                    else:
                        logger.info(f"{pagename} exists, updating wikitext")

                        @retry()
                        def do2():
                            r = page.edit(
                                volume_wikitext, comment + " (Updating metadata)"
                            )
                            assert (r or {}).get(
                                "result", {}
                            ) == "Success", f"Update failed {r}"

                        do2()
            except Exception as e:
                failcnt += 1
                logger.warning("Upload failed", exc_info=e)
                if not getopt("skip_on_failures", False):
                    raise e
            prev_filename = filename
        store_position(batch_name, book["relicno"])
    # logger.info(f"Batch done with {failcnt} failures.")


if __name__ == "__main__":
    main()
