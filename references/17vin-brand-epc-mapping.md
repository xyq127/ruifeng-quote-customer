# 17vin 品牌 EPC 映射表

从 17vin API 6001 接口获取（2026-06），共 572 个品牌。

## 中国品牌映射

| 品牌名 | EPC | hasPart |
|--------|-----|---------|
| 长安 | changan | ✅ |
| 长安欧尚 | changan | ✅ |
| 长安凯程 | changan | ✅ |
| 东风风神 | dongfeng_fengshen | ✅ |
| 东南 | dongnan | ✅ |
| 福田 | futian | ❌ |
| 福田乘用车 | futian | ❌ |
| 海马 | haima | ✅ |
| 铃木 | suzuki | ❌ |
| 奇瑞 | chery | ✅ |
| 上汽大通 | datong | ✅ |
| 雪铁龙 | citroen | ✅ |
| 小鹏 | xiaopeng | ✅ |
| 中华 | huachen | ❌ |
| 标致 | peugeot | ✅ |
| 比亚迪 | byd | ✅ |
| 吉利 | geely | ✅ |
| 长城 | greatwall | ✅ |
| 哈弗 | haval | ✅ |
| 荣威 | roewe | ✅ |
| 五菱 | wuling | ✅ |
| 广汽传祺 | gac | ✅ |
| 奇瑞开瑞 | karry | ✅ |
| 众泰 | zotye | ❌ |

## 重要发现（2026-06）

**中国品牌的 EPC 逐级查询（cata2/cata3/cata4）API 全部返回 code=1006。**
即使 cata1 正常返回（如长安CS15有11个一级目录），cata2 也返回空。

网页端 EPC 对中国品牌的二级目录也常为空（iframe 加载空数据）。

**结论**：17vin 不适合用于查询中国自主品牌的轮毂轴承 OE 号。
