#!/usr/bin/env python3
import yaml
import os
import re
import json
import sys
import functools

import mwclient

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "config.yml")
DATA_DIR = os.path.join(os.path.dirname(__file__), "../crawler")


def main():

    with open(CONFIG_FILE_PATH, "r") as f:
        config = yaml.safe_load(f.read())

    if len(sys.argv) < 2:
        exit(
            f"Not batch specified.\n\nAvailable: {', '.join(list(config['batches'].keys()))}"
        )
    batch_name = sys.argv[1]

    def getopt(item, default=None):  # get batch config or fallback to global config
        return config["batches"][batch_name].get(item, config.get(item, default))

    with open(os.path.join(DATA_DIR, batch_name + ".json")) as f:
        books = json.load(f)
    template = "Template:" + getopt("template")
    batch_link = getopt("link") or getopt("name")
    category_name = re.search(r"(Category:.+?)[]|]", batch_link).group(1)

    lines = [
        f"== {batch_name} ==",
        f"Category: {batch_link}, Template: {{{{Template|{template}}}}}, Books: {len(books)}, Files: {sum(map(lambda e: len(e['p_resourceurl'].split(',')), books))}\n",
    ]

    for book in books:
        title = book["oldname"]
        byline = book["author"]
        lines.append(f'* 《{book["oldname"]}》 {book["author"]} （{book["version"]}）')

        volurls = book["p_resourceurl"].split(",")

        for ivol, volurl in enumerate(volurls):
            # pagename = "File:" + book['name'] + ".pdf"
            volume_name = f"第{ivol+1}冊" if len(volurls) > 1 else ""
            volume_name_wps = (
                (" " + volume_name) if volume_name else ""
            )  # with preceding space
            filename = f'{book["name"]}{volume_name_wps}.pdf'
            pagename = "File:" + filename
            assert all(char not in set(r'["$*|\]</^>@#') for char in pagename)
            comment = f'Upload {book["name"]}{volume_name_wps} ({1+ivol}/{len(volurls)}) by {book["author"]} (batch task; 3gm; {batch_link}; [[{category_name}|{title}]])'
            lines.append(f"** [[:{pagename}]]")

    lines.append("")
    lines.append("[[" + category_name + "]]")
    lines.append("")

    if len(sys.argv) < 3:
        print("\n".join(lines))
    else:
        print(f"Writing file list for batch {batch_name}")
        pagename = sys.argv[2]

        username, password = config["username"], config["password"]
        site = mwclient.Site("commons.wikimedia.org")
        site.login(username, password)
        site.requests["timeout"] = 125
        site.chunk_size = 1024 * 1024 * 64

        site.pages[pagename].edit(
            "\n".join(lines), f"Writing file list for batch {batch_name} to {pagename}"
        )


if __name__ == "__main__":
    main()
