"""Non-destructive preview for the supplied September09 v2 workbook only."""
import argparse
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
from PIL import Image


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.output.resolve()==args.workbook.resolve():
        raise ValueError('Preview must be a new file')
    drawing='xl/drawings/drawing1.xml';rels='xl/drawings/_rels/drawing1.xml.rels'
    a='http://schemas.openxmlformats.org/drawingml/2006/main'
    r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    m='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(args.workbook) as source:
        tree=ET.fromstring(source.read(drawing));blip=tree.find('.//{'+a+'}blip')
        if blip is None: raise ValueError('Expected v2 evidence picture')
        rid=blip.attrib['{'+r+'}embed']
        for element in tree.iter():
            if element.tag.endswith('}cNvPr'):
                element.set('name','대책서용 전체 기판 검사 요약')
                element.set('descr','패널 없는 전체 기판 증거사진. 빨강은 확정 불량, 주황은 미확정 후보. 번호는 JSON rendering.findings와 대응.')
        with Image.open(args.image) as picture:
            ratio=picture.width/picture.height
        for element in tree.iter():
            if element.tag.endswith('}ext') and element.get('cx') and element.get('cy'):
                width,height=int(element.get('cx')),int(element.get('cy'))
                if abs(width/height-ratio)<0.001: continue
                if width/height>ratio: width=round(height*ratio)
                else: height=round(width/ratio)
                element.set('cx',str(width));element.set('cy',str(height))
        for parent in tree.iter():
            for child in list(parent):
                if child.tag=='{'+a+'}srcRect': parent.remove(child)
        relationships=ET.fromstring(source.read(rels))
        match=[el for el in relationships if el.get('Id')==rid]
        if len(match)!=1:raise ValueError('Expected one evidence relationship')
        match[0].set('Target','../media/countermeasure_preview.png')
        sheet=ET.fromstring(source.read('xl/worksheets/sheet1.xml'))
        cell=next(el for el in sheet.iter('{'+m+'}c') if el.get('r')=='A19')
        for child in list(cell):cell.remove(child)
        cell.set('t','inlineStr');inline=ET.SubElement(cell,'{'+m+'}is')
        ET.SubElement(inline,'{'+m+'}t').text='전체 기판 증거사진 · 번호는 검사 항목과 대응\n빨강: 확정 불량 / 주황: 미확정 후보'
        replacements={drawing:ET.tostring(tree),rels:ET.tostring(relationships),
                      'xl/worksheets/sheet1.xml':ET.tostring(sheet)}
        with zipfile.ZipFile(args.output,'x',compression=zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                target.writestr(item,replacements.get(item.filename,source.read(item.filename)))
            target.writestr('xl/media/countermeasure_preview.png',args.image.read_bytes())
    print(args.output)


if __name__=='__main__':main()
