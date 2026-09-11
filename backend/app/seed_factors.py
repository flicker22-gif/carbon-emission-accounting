"""预置排放因子种子数据。

因子按 (能源类型, 地区, 适用年度) 版本化。region="全国" 为兜底因子。
标记"示例值"的地区因子请在正式使用前替换为官方最新发布值
(生态环境部每年发布全国及省级电力排放因子)。
"""

DEFAULT_FACTORS = [
    # ---------- 范围一:直接排放(燃料因子全国通用) ----------
    dict(energy_type="natural_gas", name_zh="天然气", scope=1, category="固定燃烧",
         unit="m³", factor_value=2.162, region="全国", year=2024,
         source="IPCC 2006 缺省值折算", note="按低位发热值 38.93 MJ/m³ 估算"),
    dict(energy_type="diesel", name_zh="柴油", scope=1, category="移动燃烧/固定燃烧",
         unit="L", factor_value=2.68, region="全国", year=2024,
         source="DEFRA 2024", note="密度按 0.84 kg/L 折算"),
    dict(energy_type="gasoline", name_zh="汽油", scope=1, category="移动燃烧",
         unit="L", factor_value=2.31, region="全国", year=2024,
         source="DEFRA 2024", note=""),
    dict(energy_type="coal", name_zh="原煤", scope=1, category="固定燃烧",
         unit="t", factor_value=1980.0, region="全国", year=2024,
         source="IPCC 2006 缺省值折算", note="请按实际煤种低位发热值调整"),
    dict(energy_type="lpg", name_zh="液化石油气", scope=1, category="固定燃烧",
         unit="kg", factor_value=3.02, region="全国", year=2024,
         source="DEFRA 2024", note=""),
    # ---------- 范围二:外购能源(电力按地区维护) ----------
    dict(energy_type="electricity", name_zh="外购电力", scope=2, category="外购电力",
         unit="kWh", factor_value=0.5568, region="全国", year=2022,
         source="生态环境部 2022 年全国电力平均排放因子", note=""),
    dict(energy_type="electricity", name_zh="外购电力", scope=2, category="外购电力",
         unit="kWh", factor_value=0.5366, region="全国", year=2023,
         source="生态环境部 2023 年全国电力平均排放因子(示例值,请核实)", note=""),
    dict(energy_type="electricity", name_zh="外购电力", scope=2, category="外购电力",
         unit="kWh", factor_value=0.5810, region="江苏", year=2023,
         source="省级电力排放因子(示例值,请替换为官方发布值)", note=""),
    dict(energy_type="electricity", name_zh="外购电力", scope=2, category="外购电力",
         unit="kWh", factor_value=0.4712, region="广东", year=2023,
         source="省级电力排放因子(示例值,请替换为官方发布值)", note=""),
    dict(energy_type="heat", name_zh="外购热力/蒸汽", scope=2, category="外购热力",
         unit="GJ", factor_value=110.0, region="全国", year=2024,
         source="中国温室气体核算指南缺省值", note="0.11 tCO2/GJ"),
    # ---------- 范围三:其他间接排放 ----------
    dict(energy_type="water", name_zh="自来水", scope=3, category="上游间接(供水)",
         unit="m³", factor_value=0.344, region="全国", year=2024,
         source="DEFRA 2024(供水+污水处理合计)", note=""),
    dict(energy_type="business_travel_air", name_zh="航空差旅", scope=3, category="商务差旅",
         unit="人·km", factor_value=0.156, region="全国", year=2024,
         source="DEFRA 2024 国内航线均值", note=""),
    dict(energy_type="waste_general", name_zh="一般废弃物处置", scope=3, category="废弃物处置",
         unit="kg", factor_value=0.45, region="全国", year=2024,
         source="DEFRA 2024 填埋均值", note=""),
]
