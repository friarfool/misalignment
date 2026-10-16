import json
import requests
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin

BASE = "https://alignment.openai.com"
PAGE = BASE + "/misalignment-reports/?sort=created"
FEED_URL = BASE + "/misalignment-reports/rss.xml"

response = requests.get(
    PAGE,
    headers={"User-Agent": "Mozilla/5.0 (compatible; RSSFeedGenerator/1.0)"},
    timeout=30,
)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "OpenAI Misalignment Reports"
ET.SubElement(channel, "link").text = BASE + "/misalignment-reports/"
ET.SubElement(channel, "description").text = (
    "Misalignment reports and notices published by OpenAI."
)
ET.SubElement(channel, "lastBuildDate").text = format_datetime(
    datetime.now(timezone.utc)
)

items = []

for section_id, kind in [
    ("report-entries", "Report"),
    ("notice-entries", "Notice"),
]:
    section = soup.find(id=section_id)
    if not section:
        continue

    for entry in section.select(".report-entry"):
        title_link = entry.select_one("a.report-title")
        if not title_link:
            title_link = entry.select_one("a.description-content")

        if not title_link:
            continue

        title = title_link.get_text(" ", strip=True)
        link = urljoin(BASE, title_link.get("href", ""))

        detail = entry.select_one(".description-content")
        summary = ""
        if detail:
            first_paragraph = detail.find("p")
            if first_paragraph:
                summary = first_paragraph.get_text(" ", strip=True)

        topics = json.loads(entry.get("data-topics", "[]"))

        # Prefer the publication/first-posted date over the incident date.
        date_text = (
            entry.get("data-date")
            or entry.get("data-created")
            or entry.get("data-report")
        )

        if not date_text:
            time_tag = entry.select_one("time[datetime]")
            if time_tag:
                date_text = time_tag.get("datetime")

        pub_date = None
        if date_text:
            try:
                pub_date = format_datetime(
                    datetime.strptime(date_text[:10], "%Y-%m-%d")
                    .replace(tzinfo=timezone.utc)
                )
            except ValueError:
                pass

        items.append({
            "title": title,
            "link": link,
            "summary": summary,
            "topics": topics,
            "kind": kind,
            "date": pub_date,
        })

# Newest publication dates first; undated entries last.
items.sort(key=lambda x: x["date"] or "", reverse=True)

for data in items:
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = data["title"]
    ET.SubElement(item, "link").text = data["link"]
    ET.SubElement(item, "guid", isPermaLink="true").text = data["link"]
    ET.SubElement(item, "description").text = data["summary"]

    categories = [data["kind"]] + data["topics"]
    for category in categories:
        ET.SubElement(item, "category").text = category

    if data["date"]:
        ET.SubElement(item, "pubDate").text = data["date"]

ET.indent(rss, space="  ")
ET.ElementTree(rss).write(
    "rss.xml",
    encoding="utf-8",
    xml_declaration=True,
)

print(f"Created rss.xml with {len(items)} items.")
