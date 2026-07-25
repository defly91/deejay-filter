#!/usr/bin/env python3
"""
Podcast RSS filter: fetches RSS feeds, filters episodes by duration,
and generates clean filtered RSS files.
"""

import xml.etree.ElementTree as ET
import urllib.request
import sys
import os
from datetime import datetime, timezone

FEEDS = [
    {
        "name": "Deejay Chiama Italia",
        "url": "https://www.omnycontent.com/d/playlist/60311b15-274a-4e3f-8ba9-ac3000834f37/00f0707e-6a46-450e-9c24-ae3d00a6db96/7547296f-de34-47c8-817f-ae3d00a6db9f/podcast.rss",
        "min_duration": 1800,
        "output": "deejay-chiama-italia.xml",
    },
    {
        "name": "Il Volo del Mattino",
        "url": "https://www.omnycontent.com/d/playlist/60311b15-274a-4e3f-8ba9-ac3000834f37/01821ba4-b896-495c-bd4f-ae3d00a7c45d/5e153015-3c8c-423b-8593-ae3d00a7c474/podcast.rss",
        "min_duration": 1200,
        "output": "il-volo-del-mattino.xml",
    },
]

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"
MEDIA_NS = "http://search.yahoo.com/mrss/"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


def fetch_feed(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PodcastFilter/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_feed(data: bytes):
    root = ET.fromstring(data)
    channel = root.find("channel")
    return root, channel


def get_text(el, tag, ns=""):
    if ns:
        child = el.find(f"{{{ns}}}{tag}")
    else:
        child = el.find(tag)
    return child.text if child is not None else None


def get_attr(el, tag, attr, ns=""):
    if ns:
        child = el.find(f"{{{ns}}}{tag}")
    else:
        child = el.find(tag)
    return child.get(attr) if child is not None else None


def parse_duration(raw):
    if raw is None:
        return 0
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    parts = raw.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return 0
    return 0


def build_filtered_rss(channel, feed_config, kept_items):
    title = get_text(channel, "title") or feed_config["name"]
    link = get_text(channel, "link") or ""
    description = get_text(channel, "description") or ""
    author = get_text(channel, "author", ITUNES_NS) or ""
    image_url = get_attr(channel, "image", "href", ITUNES_NS) or ""
    language = get_text(channel, "language") or "it-IT"
    owner_name = ""
    owner_email = ""
    owner_el = channel.find(f"{{{ITUNES_NS}}}owner")
    if owner_el is not None:
        owner_name = get_text(owner_el, "name", ITUNES_NS) or ""
        owner_email = get_text(owner_el, "email", ITUNES_NS) or ""
    explicit = get_text(channel, "explicit", ITUNES_NS) or "no"
    category = ""
    cat_el = channel.find(f"{{{ITUNES_NS}}}category")
    if cat_el is not None:
        category = cat_el.get("text", "")

    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

    items_xml = ""
    for item in kept_items:
        item_title = get_text(item, "title") or ""
        item_desc = get_text(item, "description") or ""
        item_content = get_text(item, "encoded", CONTENT_NS) or ""
        item_pub = get_text(item, "pubDate") or ""
        item_dur = get_text(item, "duration", ITUNES_NS) or ""
        item_ep_type = get_text(item, "episodeType", ITUNES_NS) or "full"
        item_ep_num = get_text(item, "episode", ITUNES_NS) or ""
        item_season = get_text(item, "season", ITUNES_NS) or ""
        item_explicit = get_text(item, "explicit", ITUNES_NS) or "no"
        item_author = get_text(item, "author", ITUNES_NS) or ""
        item_image = get_attr(item, "image", "href", ITUNES_NS) or ""

        enclosure_el = item.find("enclosure")
        enc_url = enclosure_el.get("url", "") if enclosure_el is not None else ""
        enc_len = enclosure_el.get("length", "0") if enclosure_el is not None else "0"
        enc_type = enclosure_el.get("type", "audio/mpeg") if enclosure_el is not None else "audio/mpeg"

        guid_el = item.find("guid")
        guid_text = guid_el.text if guid_el is not None else enc_url
        guid_is_perma = guid_el.get("isPermaLink", "false") if guid_el is not None else "false"

        media_url = ""
        media_player = ""
        media_el = item.find(f"{{{MEDIA_NS}}}content")
        if media_el is not None:
            media_url = media_el.get("url", "")
            player_el = media_el.find(f"{{{MEDIA_NS}}}player")
            if player_el is not None:
                media_player = player_el.get("url", "")

        items_xml += f"""    <item>
      <title><![CDATA[{item_title}]]></title>
      <description><![CDATA[{item_desc}]]></description>
      <content:encoded><![CDATA[{item_content}]]></content:encoded>
      <pubDate>{item_pub}</pubDate>
      <enclosure url="{enc_url}" length="{enc_len}" type="{enc_type}" />
      <guid isPermaLink="{guid_is_perma}"><![CDATA[{guid_text}]]></guid>
      <itunes:duration>{item_dur}</itunes:duration>
      <itunes:episodeType>{item_ep_type}</itunes:episodeType>
      <itunes:explicit>{item_explicit}</itunes:explicit>
      <itunes:author>{item_author}</itunes:author>
"""
        if item_ep_num:
            items_xml += f'      <itunes:episode>{item_ep_num}</itunes:episode>\n'
        if item_season:
            items_xml += f'      <itunes:season>{item_season}</itunes:season>\n'
        if item_image:
            items_xml += f'      <itunes:image href="{item_image}" />\n'
        if media_url:
            items_xml += f'      <media:content url="{media_url}" type="audio/mpeg">\n'
            if media_player:
                items_xml += f'        <media:player url="{media_player}" />\n'
            items_xml += f'      </media:content>\n'
        items_xml += "    </item>\n"

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="{ITUNES_NS}" xmlns:atom="{ATOM_NS}" xmlns:media="{MEDIA_NS}" xmlns:content="{CONTENT_NS}" version="2.0">
  <channel>
    <title><![CDATA[{title}]]></title>
    <link>{link}</link>
    <description><![CDATA[{description}]]></description>
    <language>{language}</language>
    <lastBuildDate>{now}</lastBuildDate>
    <itunes:author><![CDATA[{author}]]></itunes:author>
    <itunes:owner>
      <itunes:name><![CDATA[{owner_name}]]></itunes:name>
      <itunes:email>{owner_email}</itunes:email>
    </itunes:owner>
    <itunes:image href="{image_url}" />
    <itunes:category text="{category}" />
    <itunes:explicit>{explicit}</itunes:explicit>
    <itunes:type>episodic</itunes:type>
{items_xml}  </channel>
</rss>
"""
    return rss


def process_feed(feed_config: dict, output_dir: str):
    name = feed_config["name"]
    url = feed_config["url"]
    min_dur = feed_config["min_duration"]
    output_file = feed_config["output"]

    print(f"  Fetching: {name}...")
    data = fetch_feed(url)
    root, channel = parse_feed(data)

    items = channel.findall("item")
    print(f"  Total episodes: {len(items)}")

    kept = []
    for item in items:
        dur_raw = get_text(item, "duration", ITUNES_NS)
        dur = parse_duration(dur_raw)
        if dur >= min_dur:
            kept.append(item)

    print(f"  Kept (>= {min_dur}s): {len(kept)}")

    rss_xml = build_filtered_rss(channel, feed_config, kept)
    out_path = os.path.join(output_dir, output_file)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rss_xml)
    print(f"  Written: {out_path}")
    return len(kept)


def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]

    os.makedirs(output_dir, exist_ok=True)

    print("Podcast Filter")
    print("=" * 40)
    total = 0
    for feed in FEEDS:
        print(f"\n[{feed['name']}]")
        count = process_feed(feed, output_dir)
        total += count

    print(f"\n{'=' * 40}")
    print(f"Done. {total} episodes kept across {len(FEEDS)} feeds.")


if __name__ == "__main__":
    main()
