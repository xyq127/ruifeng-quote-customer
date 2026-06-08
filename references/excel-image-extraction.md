# Excel 内嵌图片提取：按列值命名

## 适用场景

从产品目录 Excel 中提取内嵌图片（位于单元格内的图片），并以产品编码/编号列的值作为文件名保存。

## 技术原理

Excel (.xlsx) 是一个 ZIP 包，图片存储在 `xl/media/` 目录下。`drawing1.xml` 描述每张图片的单元格锚点（`<xdr:from><xdr:col><xdr:row>`），`drawing1.xml.rels` 将 `rId` 映射到图片文件路径。

## 工作流

```python
import zipfile
import xml.etree.ElementTree as ET
import openpyxl
import os

path = "目录.xlsx"
out_dir = "导出目录"
os.makedirs(out_dir, exist_ok=True)

# 1. 读取产品编码列（Excel 行号 → 产品编码）
wb = openpyxl.load_workbook(path)
ws = wb['Sheet1']  # 或 wb.active
row_to_product = {}
for r in range(1, ws.max_row + 1):
    val = ws.cell(row=r, column=5).value  # Column E
    if val is not None:
        row_to_product[r] = str(val).strip()

# 2. 读取 drawing 关系（rId → 图片文件名）
with zipfile.ZipFile(path, 'r') as z:
    rels_xml = z.read('xl/drawings/_rels/drawing1.xml.rels')
    ns_rels = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
    rid_to_target = {}
    for rel in ET.fromstring(rels_xml):
        rid = rel.attrib.get('Id')
        target = rel.attrib.get('Target', '').replace('../media/', '')
        if rid and target:
            rid_to_target[rid] = target

    # 3. 读取 drawing XML 获取每个图片的锚点
    drawing_xml = z.read('xl/drawings/drawing1.xml')
    ns = {
        'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    }
    image_placements = ET.fromstring(drawing_xml).findall('.//xdr:twoCellAnchor', ns)

    # 4. 缓存所有图片二进制
    image_cache = {}
    for mf in [f for f in z.namelist() if f.startswith('xl/media/') and f != 'xl/media/']:
        name = mf.replace('xl/media/', '')
        image_cache[name] = z.read(mf)

    # 5. 保存图片
    for anchor in image_placements:
        from_elem = anchor.find('.//xdr:from', ns)
        col = int(from_elem.find('xdr:col', ns).text)  # 0-indexed
        row = int(from_elem.find('xdr:row', ns).text) + 1  # → 1-indexed
        if col != 1:  # 只处理 B 列（产品图片列）
            continue

        product_code = row_to_product.get(row)
        if product_code is None:
            continue

        blip = anchor.find('.//a:blip', ns)
        r_id = blip.attrib.get(f'{{http://schemas.openxmlformats.org/officeDocument/2006/relationships}}embed')
        media_name = rid_to_target.get(r_id)
        img_data = image_cache.get(media_name)
        if img_data is None:
            continue

        ext = os.path.splitext(media_name)[1].replace('.jpeg', '.jpg')
        filename = f"{product_code}{ext}"
        filepath = os.path.join(out_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(img_data)
```

## 关键点

- **列号 0-indexed**：`<xdr:col>` 中 col=0=A, col=1=B, col=2=C
- **行号转化**：drawing XML 中 `<xdr:row>` 是 0-indexed，openpyxl 中 `ws.cell(row=X, ...)` 是 1-indexed
- **列 B vs 列 C**：产品图片和参考图分别在不同列，通过 `col` 区分
- **重复图片处理**：同一产品编码在 Excel 中可能有多个 OEM 行，图片可能是重复的（同一 rId 多次引用）。去重逻辑：按 `(product_code, media_name)` 去重，多个不同图片用 `_N` 后缀
- **图片格式**：`rId` → 文件名中有 `.jpeg` / `.png` / `.emf`，保存时应保持原扩展名
- **378 图片限制**：openpyxl 的 `_images` 列表只返回前 378 个。要获取全部 579+ 图片必须通过 zipfile 直接读取
