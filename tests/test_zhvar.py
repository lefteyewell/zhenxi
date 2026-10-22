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
"""zhvar 繁简变体表测试（0.5.59）。

覆盖：
- 表规模与常用字覆盖
- 繁→简正确性（含 Unihan 缺失的人工补充对）
- 一简对多繁全展开（相对 zhconv 的核心增益）
- variants() 契约（原文+简体+繁体、标点剥离、封顶）
- 与 zhconv 的对比回归（若已安装）：单字层面我们的展开是 zhconv 选择的超集
"""

import unittest

from photo_manager.core import zhvar

# 常用简体字样本（覆盖测试基准）
COMMON = (
    "国爱安暗坝罢摆办绊帮绑谤苞饱宝报鲍贝备倍奔苯本逼鼻比彼笔币毕闭辟边编变辩标鳖瘪别滨宾摈饼拨钵驳补布"
    "才财采参蚕残惭惨灿苍舱仓沧厕侧测层搀谗馋缠铲产阐颤场尝长偿肠厂畅钞车彻尘陈衬撑称惩痴迟齿耻虫丑筹出"
    "处触疮辞聪丛凑窜错达呆带贷担单郸掸胆惮弹当挡党荡导灯邓敌涤递缔点垫电淀钓调迭谍叠钉顶锭订东动冻斗独"
    "读赌肚断队对吨顿夺堕鹅额讹恶饿儿尔饵贰发罚阀珐矾烦范饭访纺飞废费纷坟奋愤粪丰风疯峰锋风冯逢缝凤妇复"
    "赋负驸钙盖干赶秆赣冈刚钢纲岗皋镐搁鸽阁铬个巩贡沟钩构购够蛊谷顾剐挂关观馆惯贯广垭归龟规诡贵刽辊滚"
    "国过海尔骇汉号阂鹤贺横轰红后壶护沪户护华划画话怀坏欢环还缓换唤痪焕涣黄谎挥辉毁贿秽会烩汇讳诲绘荤"
    "浑伙获货祸击机积饥迹讥鸡绩缉极辑级挤几蓟剂济计记际继纪荚颊贾钾价驾歼监坚笺间艰缄茧检碱硷拣捡简俭"
    "减荐槛鉴践贱见键舰剑饯渐溅涧浆将桨蒋讲奖酱胶浇骄娇搅铰矫侥脚饺缴绞轿较阶节洁结诫届紧锦仅谨进尽劲荆"
    "觉绝军骏开凯颗壳课垦恳夸块宽况旷矿亏馈岿窥溃扩腊蜡来赖兰拦栏烂滥劳痨乐垒类泪篱离里鲤礼丽厉励砾历"
    "沥隶俩联莲连镰怜涟帘敛脸链恋炼练粮凉两辆谅疗辽镣猎临邻鳞凛赁龄铃凌灵岭领刘娄楼芦卢颅庐炉掳卤虏"
    "鲁赂禄录陆驴吕铝侣屡缕虑滤绿峦挛孪滦乱抡轮伦仑沦纶论萝罗逻锣箩骡骆妈玛码蚂马骂吗买麦卖迈脉瞒馒"
    "蛮满谩猫锚铆贸么霉门闷们锰梦谜弥觅绵缅庙灭悯闽铭谬谋亩钠纳难挠脑恼闹馁内拟你昵逆酿鸟聂啮镍宁拧"
    "泞钮纽脓浓农疟诺欧鸥殴呕沤盘庞赔喷鹏骗飘频贫苹凭扑铺朴谱脐齐骑岂启气弃讫牵扦钎铅迁签谦钱钳潜浅谴"
    "堑枪呛墙蔷强抢锹桥侨窍翘窃钦亲轻氢倾顷请庆琼穷秋丘邱球求囚区蛆趋躯龋劝券缺却鹊确让饶扰绕热壬仁认"
    "刃纫韧任荣绒软锐闰润洒萨飒腮鳃赛伞丧扫涩杀纱筛晒闪陕赡缮伤赏烧绍赊摄慑设绅审婶肾渗声绳胜圣师狮"
    "湿诗时蚀实识驶势适释饰视试寿兽枢输书赎属术树竖数帅双谁税顺说硕丝饲厮四讼诵诉苏肃虽随绥岁孙损笋"
    "缩琐锁獭挞抬台态摊贪瘫滩坛谭谈叹汤烫涛绦讨腾誊锑题体屉条贴铁厅听烃铜统头图涂团颓蜕脱驮驼椭洼袜"
    "弯湾玩顽万挽晚碗万汪网韦违围为潍维苇伟伪纬谓卫温闻文稳问瓮挝蜗涡窝呜钨乌诬无芜吴坞雾务误锡牺袭"
    "习铣戏细虾辖峡侠狭厦吓鲜纤咸贤衔闲显险现献县馅羡宪线限乡相详响项萧销晓啸蝎协挟谐胁泻亵谢锌衅兴汹"
    "锈绣虚嘘须许绪续轩悬选癣绚学勋询寻驯训讯逊压鸦鸭哑亚讶阉烟盐严颜阎艳厌砚彦谚验鸯杨扬疡阳痒养样瑶"
    "摇尧遥窑谣药爷页业叶医铱颐遗仪彝蚁艺亿忆义诣议谊译异绎阴银饮隐婴樱鹰荧蝇颖哟拥佣痈踊咏涌优忧邮铀"
    "犹游诱于舆鱼渔娱与屿语狱誉预驭鸳渊辕园员圆缘远愿约跃钥岳粤悦阅云郧运陨酝晕韵杂灾载攒赞赃脏凿枣灶"
    "责择则泽贼赠扎札轧铡闸诈斋债毡盏斩辗崭栈战绽张涨帐账胀赵蛰辙锗这贞针侦诊镇阵挣睁狰争帧症郑证织职"
    "执纸挚掷帜质钟终种肿众诌轴皱昼骤珠诸猪烛嘱嘱铸驻专砖转赚桩庄装妆壮状锥赘坠缀谆准浊兹资渍踪综总纵"
    "邹诅组钻"
)


class TestScale(unittest.TestCase):
    def test_table_size(self):
        self.assertGreater(len(zhvar._T2S), 2500)
        multi = sum(1 for v in zhvar._S2T.values() if len(v) > 1)
        self.assertGreater(multi, 50)

    def test_common_coverage(self):
        """常用简体字中，有繁体对应者的覆盖率应 ≥ 95%。"""
        covered = sum(1 for c in set(COMMON) if c in zhvar._S2T)
        self.assertGreater(covered / len(set(COMMON)), 0.95)


class TestToSimp(unittest.TestCase):
    def test_common_pairs(self):
        cases = {
            "海邊": "海边", "髮型": "发型", "後臺": "后台", "臺灣": "台湾",
            "軟體開發": "软件开发", "乾杯": "干杯", "五嶽": "五岳",
            "遊客": "游客", "記錄": "记录", "分佈": "分布", "勳章": "勋章",
            "湧現": "涌现", "蠍子": "蝎子", "羨慕": "羡慕", "甕中": "瓮中",
        }
        for trad, simp in cases.items():
            self.assertEqual(zhvar.to_simp(trad), simp, trad)

    def test_non_chinese_passthrough(self):
        self.assertEqual(zhvar.to_simp("abc123_-"), "abc123_-")
        self.assertEqual(zhvar.to_simp(""), "")

    def test_unmapped_char_passthrough(self):
        # 共享字（无繁简对应）原样保留
        self.assertEqual(zhvar.to_simp("海文球汪"), "海文球汪")


class TestMultiVariant(unittest.TestCase):
    def test_full_expansion(self):
        """一简对多繁全展开（zhconv 只给一个最可能字形）。"""
        self.assertEqual(set(zhvar._S2T["台"]), {"臺", "檯", "颱"})
        self.assertEqual(set(zhvar._S2T["发"]), {"發", "髮"})
        self.assertEqual(set(zhvar._S2T["干"]), {"幹", "乾"})
        self.assertEqual(set(zhvar._S2T["复"]), {"復", "複", "覆"})
        self.assertEqual(set(zhvar._S2T["系"]), {"係", "繫"})
        self.assertEqual(set(zhvar._S2T["里"]), {"裡", "裏"})

    def test_trad_variants_order(self):
        """主序优先：首选繁体形在首位。"""
        self.assertEqual(zhvar.trad_variants("台")[0], "臺")
        self.assertEqual(zhvar.trad_variants("发")[0], "發")


class TestVariants(unittest.TestCase):
    def test_contract_simplified_query(self):
        v = zhvar.variants("海边")
        self.assertEqual(v[0], "海边")  # 原文在前
        self.assertIn("海邊", v)

    def test_contract_traditional_query(self):
        v = zhvar.variants("海邊")
        self.assertEqual(v[0], "海邊")
        self.assertIn("海边", v)

    def test_multi_variant_in_variants(self):
        v = zhvar.variants("发型")
        self.assertIn("發型", v)
        self.assertIn("髮型", v)

    def test_punct_strip(self):
        v = zhvar.variants("「海边」")
        self.assertEqual(v[0], "「海边」")  # 原文保留
        self.assertIn("海边", v)  # 剥离标点后的附加变体

    def test_cap_no_explosion(self):
        """10 个多繁字连查也不爆炸（封顶 1 原文 + 1 简体 + 6 繁体）。"""
        v = zhvar.variants("台发干复系表里汇历尽")
        self.assertLessEqual(len(v), 8)

    def test_dedup(self):
        v = zhvar.variants("海邊")  # 繁体输入的简体形=去重后不重复
        self.assertEqual(len(v), len(set(v)))

    def test_edge_cases(self):
        self.assertEqual(zhvar.variants(""), [])
        self.assertEqual(zhvar.variants("abc"), ["abc"])
        self.assertEqual(zhvar.trad_variants(""), [])


class TestPhrases(unittest.TestCase):
    """地区词汇短语表（0.5.60）。"""

    def test_simplified_query_expansion(self):
        """简体查询展开到 TW/HK 繁体地区词汇。"""
        v = zhvar.variants("软件")
        self.assertIn("軟體", v)
        self.assertIn("軟件", v)
        v = zhvar.variants("网络")
        self.assertIn("網路", v)
        v = zhvar.variants("视频")
        self.assertIn("影片", v)
        v = zhvar.variants("出租车")
        self.assertIn("計程車", v)
        self.assertIn("的士", v)

    def test_traditional_query_expansion(self):
        """繁体查询互通：→ 简体 + 其他地区变体。"""
        v = zhvar.variants("軟體")
        self.assertIn("软件", v)
        self.assertIn("軟件", v)
        v = zhvar.variants("軟件")
        self.assertIn("软件", v)
        self.assertIn("軟體", v)
        v = zhvar.variants("網路")
        self.assertIn("网络", v)
        self.assertIn("網絡", v)
        v = zhvar.variants("影片")
        self.assertIn("视频", v)

    def test_to_simp_phrase_aware(self):
        self.assertEqual(zhvar.to_simp("軟體開發"), "软件开发")
        self.assertEqual(zhvar.to_simp("網路購物"), "网络购物")
        self.assertEqual(zhvar.to_simp("行動硬碟"), "移动硬盘")
        self.assertEqual(zhvar.to_simp("智慧型手機"), "智能型手机")
        self.assertEqual(zhvar.to_simp("印表機設定"), "打印机设置")

    def test_phrase_plus_char_combo(self):
        """短语 + 一简对多繁组合（軟體髮型 等文档形态）。"""
        v = zhvar.variants("软件发型")
        self.assertIn("軟體髮型", v)
        self.assertIn("軟件髮型", v)

    def test_phrase_multi_word(self):
        """查询含多个短语：各组合形态均覆盖。"""
        v = zhvar.variants("软件设置")
        for expect in ("軟體設定", "軟件設定", "軟體設置", "軟件設置"):
            self.assertIn(expect, v)

    def test_phrase_cap(self):
        """多短语查询不爆炸。"""
        v = zhvar.variants("软件网络打印机硬盘鼠标")
        self.assertLessEqual(len(v), 20)

    def test_longest_match(self):
        """最长匹配：存储卡/内存卡 优先于 存储/内存（两者皆为正简形）。"""
        self.assertIn(zhvar.to_simp("記憶卡"), ("存储卡", "内存卡"))
        self.assertEqual(zhvar.to_simp("行動硬碟"), "移动硬盘")
        self.assertEqual(zhvar.to_simp("固態硬碟"), "固态硬盘")

    def test_table_size(self):
        self.assertGreater(len(zhvar._PHRASES_S2T), 100)
        # 单变体条目必须是元组（防裸字符串回归）
        for k, vs in zhvar._PHRASES_S2T.items():
            self.assertIsInstance(vs, tuple, k)


class TestVsZhconv(unittest.TestCase):
    """与 zhconv 的对比回归（zhconv 已不在依赖中，仅测试环境保留作基准）。"""

    @classmethod
    def setUpClass(cls):
        try:
            from zhconv.zhconv import convert as zc
            cls.zc = staticmethod(zc)
        except Exception:
            raise unittest.SkipTest("zhconv 未安装，跳过对比")

    def test_superset_of_zhconv_single_char(self):
        """单字层面：zhconv 的繁体选择应落在我们的展开集合内（召回不降）。"""
        hit = total = 0
        for ch in set(COMMON):
            if ch not in zhvar._S2T:
                continue
            z_trad = self.zc(ch, "zh-tw")
            total += 1
            if z_trad == ch or z_trad in zhvar._S2T[ch]:
                hit += 1
        self.assertGreater(total, 300)
        self.assertGreater(hit / total, 0.95)

    def test_to_simp_agreement(self):
        """繁→简与 zhconv 的一致率（常用字层面）。"""
        agree = total = 0
        for ch in set(COMMON):
            for trad in zhvar._S2T.get(ch, []):
                total += 1
                if self.zc(trad, "zh-cn") == zhvar.to_simp(trad):
                    agree += 1
        self.assertGreater(total, 300)
        self.assertGreater(agree / total, 0.95)


if __name__ == "__main__":
    unittest.main()
