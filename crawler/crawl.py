import requests
import itertools
import sys
import json
import os

PAGE_SIZE = 8
DIRECTORY_API_URL = "http://www.3gmuseum.cn/web/ancient/findAncientPage.do"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "./books.json")


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def main():
    books = []
    count = 0
    for no in itertools.count(start=1):
        r = requests.post(
            DIRECTORY_API_URL, data={"pageNumber": no, "pageSize": PAGE_SIZE}
        )
        d = r.json()
        count = d["count"]
        books.extend(d["list"])
        if not d["list"]:
            break
        eprint(f"INFO: Got {len(d['list'])} on page {no}")
    if count != len(books):
        eprint(f"WARNING: expected {count}, got {len(books)}")
    eprint("INFO: Writing to " + OUTPUT_PATH)
    with open(OUTPUT_PATH, "w+") as f:
        json.dump(books, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
