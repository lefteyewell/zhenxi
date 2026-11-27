# -*- coding: utf-8 -*-
"""地名显示层映射测试（0.7.8）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from photo_manager.core.geocode import localized_name


class LocalizeTest(unittest.TestCase):
    def test_known_names(self):
        self.assertEqual(localized_name("Taiwan"), "中国台湾")
        self.assertEqual(localized_name("Hong Kong"), "中国香港")
        self.assertEqual(localized_name("Macao"), "中国澳门")
        self.assertEqual(localized_name("Macau"), "中国澳门")

    def test_unknown_unchanged(self):
        self.assertEqual(localized_name("France"), "France")
        self.assertEqual(localized_name(""), "")
        self.assertIsNone(localized_name(None))

    def test_format_city_only(self):
        """0.7.8b：建议地名只输出城市级，不含国家/地区层级。"""
        from photo_manager.core.geocode import GeoCoder
        td = tempfile.mkdtemp()  # GeoCoder 持有 sqlite 连接，Win 下不能随 with 删除
        if True:
            db = os.path.join(td, "geo.sqlite")
            # 造最小库：countries + aliases + places（_format 只查 aliases）
            import sqlite3
            c = sqlite3.connect(db)
            c.execute("CREATE TABLE countries(code TEXT, name TEXT)")
            c.execute("CREATE TABLE aliases(geoname_id INTEGER, alias TEXT, country TEXT, kind TEXT)")
            c.execute("INSERT INTO countries VALUES('TW','Taiwan')")
            c.commit(); c.close()
            g = GeoCoder(db)
            rec = {"geoname_id": 1, "ascii_name": "Taipei", "name": "Taipei",
                   "admin1": "Taiwan", "country": "TW"}
            out = g._format(rec, 2.0)
            self.assertEqual(out, "Taipei", out)
            self.assertNotIn("中国台湾", out)
            # 远距离仍带参考距离提示
            out2 = g._format(rec, 80.0)
            self.assertTrue(out2.startswith("Taipei · 约80km"), out2)


if __name__ == "__main__":
    unittest.main()
