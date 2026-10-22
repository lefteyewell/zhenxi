# -*- coding: utf-8 -*-
# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""下载 Wikimedia Commons 公开活动照片作测试数据（HD，≥1080）。

背景：commons.wikimedia.org 在境内被屏蔽且本机代理间歇故障，
故图片经 wsrv.nl 图片代理服务端抓取（该站可直连）。
文件清单来自 Commons 类别页（精确文件名与尺寸已核对 ≥1080）。

输出：test_data_conference/<活动>/<序号>_<文件名>.jpg
每个活动按不同摄影师/不同拍摄对象选取，保证 ≥3 种拍摄角度。
"""
import csv
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "test_data_conference"

# (活动目录, 目标张数, [Commons 文件标题（File: 后缀部分）...])
EVENTS = [
    ("01_gamescom_2019", 7, [
        "American Truck Simulator Gamescom 2019 (48605662641).jpg",
        "AORUS Team Up Gamescom 2019 (48605834662).jpg",
        "AORUS VR racing simulator Gamescom 2019 (48605696576).jpg",
        "Apex Legends gaming Gamescom 2019 (48605673176).jpg",
        "Asiatische Speisen Gamescom 2019 (48605670251).jpg",
        "Benq Gaming Curve Monitor Gamescom 2019 (48605730601).jpg",
        "Best action game Doom Eternal Gamescom 2019 (48605874122).jpg",
        "Borderland 3 Gamescom 2019 (48605921707).jpg",
        "Doom Eternal Gamescom 2019 (48605731876).jpg",
        "EA Sports 2019 Chef Jens Kosche (48605680971).jpg",
        "ESL stage Gamescom 2019 (48605708741).jpg",
    ]),
    ("02_comiccon_2019", 7, [
        "Kevin Dowling (48484937857).jpg",
        ("Lynette Rice, Elgin James, Kevin Dowling, J. D. Pardo, Clayton Cardenas, "
         "Edward James Olmos, Sarah Bolger, Danny Pino, Emilio Rivera, Michael Irby, "
         "Raoul Trujillo, Antonio Jaramillo, Frankie Loyal Delgado, Joseph Lucero, "
         "Vincent V.jpg"),
        "Michael Irby, Raoul Trujillo & Antonio Jaramillo (48484788906).jpg",
        "Michael Marisi Ornstein (48484787386).jpg",
        "Sarah Bolger (48484809431).jpg",
        "Vincent \"Rocco\" Vargas & Michael Marisi Ornstein (48484939542).jpg",
        "Dafne Keen (48383634306).jpg",
        "Dafne Keen, Ruth Wilson, Lin-Manuel Miranda & James McAvoy (48383727177).jpg",
        "James McAvoy (48383600461).jpg",
        "Jenna Elfman (48403583421).jpg",
        "Lennie James (48403602631).jpg",
        ("Maggie Grace, Jenna Elfman, Austin Amelio, Alexa Nisenson, "
         "Ruben Blades & Karen David (48403750571).jpg"),
        "'The Good Place' cast and crew visit San Diego Comic Con for a panel (48469770596).jpg",
        "'The Good Place' cast and crew visit San Diego Comic Con for a panel (48469771081).jpg",
    ]),
    ("03_wikimania_2019", 7, [
        "Wikimania 2019 - Hackathon - Opening (1).jpg",
        "Wikimania 2019 - Hackathon - Opening (2).jpg",
        "Wikimania-hackathon-opening-2019-navigating.jpg",
        "Wikimania-hackathon-opening-open-mic-2019.jpg",
        "Wikimania2019dia1byEzarate.17.jpg",
        "Wikimania 2019 closing ceremony - Jimmy Wales.jpg",
        "Jimmy Wales at Wikimania 2019. Photo 70 by Alina Vozna.jpg",
        "Nodir Ataev and Jimmy Wales at Wikimania 2019.jpg",
        "Wikimania 2019 group shooters 1 jeh.jpg",
        ("Structured Data on Commons data modelling session at the Wikimania 2019 "
         "Hackathon - group discussing copyright modelling.jpg"),
        "Surstromming at Wikimania (72521).jpg",
        "Wikimania 2019 Day 06 - Aula Magna Hall.jpg",
    ]),
    ("04_ces_2025", 7, [
        "CES 2025 - LVCC 01.jpg",
        "CES 2025 - Steve Aoki 01.jpg",
        "CES 2025 - Steve Aoki 02.jpg",
        "CES 2025 - Xiaopeng 01.jpg",
        "CES 2025 - Kubota 01.jpg",
        "CES 2025 Attendance.jpg",
        "CES Unveiled Entrance - Consumer Electronics Show 2025 Las Vegas.jpg",
        "CES 2025 - Catepillar 972 01.jpg",
        "CES 2025 Gwangju Joint Pavilion Online Opening Ceremony 20250108 (01).jpg",
    ]),
    ("05_oktoberfest_munich", 7, [
        "München 2012 (173).jpg",
        "Achterbahn in Oktoberfest 2012.jpg",
        "Blick auf die Oktoberfestwiese mit Achterbahn im Hintergrund.jpg",
        "Oktoberfest (Wiesn) Paulaner Tent Trash.jpg",
        "Cheers at Oktoberfest - Flickr - GregTheBusker.jpg",
        "Blanks (11430481746) (3).jpg",
        "München, Oktoberfest 2023, Festzelt Goldener Hahn, 1.jpeg",
        "Eingang in ein Oktoberfestzelt am Samstag.JPG",
        "Oktoberfest2006.jpg",
    ]),
    ("06_venice_carnival", 7, [
        "Carnival of Venice. 2018-02-13 12-57-58.jpg",
        "CARNAVAL de VENISE 2018 IMG 0184.jpg",
        "Carnival of Venice 04.jpg",
        "Carnival masks Venice in 2011 (1).jpg",
        "Carnevale Venezia 2007.jpg",
        "Costume of the Venice carnival J1.jpg",
        ("Venetian Carnival Mask - Maschera di Carnevale - Venice Italy - "
         "Creative Commons by gnuckx (4816127343).jpg"),
        ("Venetian Carnival Mask - Maschera di Carnevale - Venice Italy - "
         "Creative Commons by gnuckx (4816703230).jpg"),
        "Venezia-Carnevale-Gnaga Mask.jpg",
    ]),
    ("07_rio_carnival_2011", 4, [
        "Carnival of Rio de Janeiro 2011 - (6776095152).jpg",
        "Carnival of Rio de Janeiro 2011 - (6776103468).jpg",
        "Carnival of Rio de Janeiro 2011 - 3rd Wing- Undines - Water Dance (6922209043).jpg",
        "Carnival of Rio de Janeiro 2011 - 6th Wing- The Whirling Ladies (6776054654).jpg",
        "Carnival of Rio de Janeiro 2011 - ala das Baianas (6922155391).jpg",
        "Carnival of Rio de Janeiro 2011 - (6922156029).jpg",
    ]),
    ("08_rio2016_olympics_100m", 4, [
        "Usain Bolt Rio 100m final 2016b.jpg",
        "Usain Bolt Rio 100m final 2016d.jpg",
        "Usain Bolt Rio 100m final 2016e.jpg",
        "Usain Bolt Rio 100m final 2016f.jpg",
        "Usain Bolt Rio 100m final 2016g.jpg",
        "Usain Bolt Rio 100m final 2016i.jpg",
        "Justin Gatlin Rio 100m final 2016.jpg",
        "De Grasse and Bolt Rio 100m final 2016.jpg",
        "Usain Bolt Rio 100m final 2016.jpg",
        "Justin Gatlin Rio 100m final 2016b.jpg",
    ]),
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 PhotoManagerTest/1.0")
# 直连（绕过本机故障代理）
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def wsrv_url(file_title: str) -> str:
    inner = ("commons.wikimedia.org/wiki/Special:FilePath/"
             + urllib.parse.quote(file_title))
    return ("https://wsrv.nl/?url=" + urllib.parse.quote(inner, safe="")
            + "&w=1920&q=88&output=jpg")


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name)
    return name[:110].strip("._ ")


def fetch(url: str, dest: Path, tries: int = 8) -> bool:
    """wsrv 直连存在间歇性 TLS 重置（实测约 1 分钟内会放行一波），
    因此对单文件做多次重试。"""
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with OPENER.open(req, timeout=90) as resp, \
                    open(dest, "wb") as fh:
                fh.write(resp.read())
            return dest.stat().st_size > 30_000
        except Exception as exc:  # noqa: BLE001
            print(f"  attempt {attempt} FAIL: {type(exc).__name__}: "
                  f"{str(exc)[:90]}", flush=True)
            time.sleep(min(6 * attempt, 30))
    return False


def main() -> int:
    OUT.mkdir(exist_ok=True)
    rows = []
    total = 0
    plan = [(folder, want, titles) for folder, want, titles in EVENTS]
    # 两轮：第二轮只补抓未达标的活动（wsrv 间歇性重置，首轮可能失败一批）
    for round_no in (1, 2):
        for folder, want, titles in plan:
            edir = OUT / folder
            edir.mkdir(exist_ok=True)
            got = sum(
                1 for t in titles
                if (edir / f"{folder[3:5]}_{sanitize(t[:60])}.jpg").exists())
            if got >= want and round_no == 2:
                continue
            for title in titles:
                if got >= want:
                    break
                dest = edir / f"{folder[3:5]}_{sanitize(title[:60])}.jpg"
                print(f"[r{round_no} {folder}] {title[:60]} ...", flush=True)
                if dest.exists() and dest.stat().st_size > 30_000:
                    ok = True
                else:
                    ok = fetch(wsrv_url(title), dest)
                if ok:
                    try:
                        with Image.open(dest) as im:
                            im.load()
                            w, h = im.size
                        if min(w, h) < 1080:
                            print(f"  too small {w}x{h}, drop", flush=True)
                            dest.unlink(missing_ok=True)
                            continue
                        rows.append([folder, dest.name, title, f"{w}x{h}",
                                     dest.stat().st_size,
                                     "https://commons.wikimedia.org/wiki/File:"
                                     + urllib.parse.quote(title)])
                        got += 1
                        print(f"  OK {w}x{h} "
                              f"({dest.stat().st_size // 1024}KB) "
                              f"[{got}/{want}]", flush=True)
                    except Exception as exc:  # noqa: BLE001
                        print(f"  bad image: {exc}", flush=True)
                        dest.unlink(missing_ok=True)
                time.sleep(1.2)
            print(f"[r{round_no} {folder}] got {got}/{want}", flush=True)
    total = len(rows)

    with open(OUT / "manifest.csv", "w", newline="", encoding="utf-8-sig") as f:
        wtr = csv.writer(f)
        wtr.writerow(["event", "file", "commons_title", "size_px",
                      "bytes", "source_page"])
        wtr.writerows(rows)

    with open(OUT / "ATTRIBUTIONS.md", "w", encoding="utf-8") as f:
        f.write("# 测试图片来源与署名\n\n"
                "全部照片来自 Wikimedia Commons（CC BY / CC BY-SA / 公有领域等"
                "自由授权），仅作本地软件测试用途。\n"
                "每张照片的原始文件页与作者信息见 manifest.csv 的 source_page 列"
                "（打开文件页即可见作者与许可证）。\n\n")
        cur = None
        for r in rows:
            if r[0] != cur:
                cur = r[0]
                f.write(f"\n## {cur}\n\n")
            f.write(f"- {r[2]} — [{r[3]}]({r[5]})\n")

    print(f"\nTOTAL={total}", flush=True)
    return 0 if total >= 50 else 2


if __name__ == "__main__":
    sys.exit(main())
